"""Публичное прохождение: /s/<токен публикации>. Ключ прохождения - в заголовке X-Response-Token."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sk_common.auth.router import client_info
from sk_common.deps import CurrentUser, Db, OptionalUser
from sk_common.redis import get_redis, hit_limit

from app.core.config import settings
from app.modules.responses import service
from app.modules.responses.schemas import AnswerIn, AnswerOut, PublicSurvey, ResponseState, StartResult, SubmitResult
from app.modules.surveys.permissions import editable_survey

preview_router = APIRouter(prefix='/v1/surveys', tags=['surveys'])


@preview_router.get('/{survey_id}/preview', response_model=PublicSurvey, summary='Предпросмотр опроса')
async def preview(survey_id: int, db: Db, user: CurrentUser) -> PublicSurvey:
    survey, _ = await editable_survey(db, survey_id, user)
    return await service.survey_form(db, survey, is_anonymous=survey.is_anonymous)


router = APIRouter(prefix='/v1/public', tags=['public'])

ResponseToken = Annotated[str | None, Header(alias='X-Response-Token')]


@router.get('/s/{token}', response_model=PublicSurvey, summary='Опрос по публичной ссылке')
async def get_survey(token: str, db: Db, user: OptionalUser) -> PublicSurvey:
    publishing = await service.open_publishing(db, token)
    return await service.public_survey(db, publishing, user)


@router.post('/s/{token}/responses', response_model=StartResult, status_code=201, summary='Начать прохождение')
async def start(token: str, request: Request, db: Db, user: OptionalUser) -> StartResult:
    publishing = await service.open_publishing(db, token)
    _, ip = client_info(request)
    if (
        publishing.is_anonymous
        and ip
        and await hit_limit(get_redis(), f'survey-start:{publishing.id}:{ip}', settings.responses_per_ip_hour, 3600)
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, 'Слишком много прохождений с этого адреса. Попробуйте позже.'
        )
    result = await service.start_response(db, publishing, user)
    await db.commit()
    return result


@router.get('/responses/current', response_model=ResponseState, summary='Сохранённые ответы прохождения')
async def current(db: Db, http_response: Response, x_response_token: ResponseToken = None) -> ResponseState:
    response = await service.response_by_token(db, x_response_token)
    http_response.headers['Cache-Control'] = 'no-store'
    return service.response_state(response)


@router.put('/responses/current/answers/{question_id}', response_model=AnswerOut, summary='Сохранить ответ')
async def save_answer(question_id: int, payload: AnswerIn, db: Db, x_response_token: ResponseToken = None) -> AnswerOut:
    response = await service.response_by_token(db, x_response_token, lock=True)
    answer = await service.save_answer(db, response, question_id, payload)
    await db.commit()
    await db.refresh(answer, ['selected_options', 'ranking'])
    return AnswerOut.model_validate(answer)


@router.post('/responses/current/submit', response_model=SubmitResult, summary='Отправить ответы')
async def submit(db: Db, x_response_token: ResponseToken = None) -> SubmitResult:
    response = await service.response_by_token(db, x_response_token, lock=True)
    publishing = await service.submit(db, response)
    await db.commit()
    return SubmitResult(status=response.status, thank_you_text=publishing.survey.thank_you_text)

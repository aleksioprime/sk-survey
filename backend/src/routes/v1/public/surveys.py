"""
Публичные эндпоинты опросов.

Все маршруты доступны без авторизации — используются для анонимного
прохождения опросов по публичному токену из survey_publishings.
"""

from fastapi import APIRouter, Query

from src.schemas import AnswerPayload
from src.services.survey_service import survey_service

router = APIRouter()


@router.get('/{token}')
async def get_survey_bundle(token: str, response_token: str | None = Query(default=None)):
    """Получить полный бандл опроса по публичному токену.
    Если передан response_token — подгрузить существующие ответы для возобновления."""
    return await survey_service.get_bundle(token, response_token=response_token)


@router.post('/{token}/start')
async def start_response(token: str):
    """Начать прохождение: создать новый response."""
    return await survey_service.start_response(token)


@router.patch('/{token}/responses/{response_id}/answers/{question_id}')
async def save_answer(token: str, response_id: int, question_id: int, payload: AnswerPayload):
    """Сохранить/обновить ответ на вопрос."""
    return await survey_service.save_answer(token, response_id, question_id, payload)


@router.post('/{token}/responses/{response_id}/submit')
async def submit_response(token: str, response_id: int):
    """Отправить завершённый ответ."""
    return await survey_service.submit_response(token, response_id)

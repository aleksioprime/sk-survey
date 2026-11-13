"""Прохождение опроса по публичной ссылке.

Анонимная публикация: прохождение начинается без входа, браузер получает ключ прохождения и хранит его;
сервер знает только хеш ключа. Без ключа нельзя ни прочитать, ни изменить, ни отправить чужие ответы.
Неанонимная: нужен вход через SkolStream, у человека одно прохождение публикации.
"""

import math

import nh3
from fastapi import HTTPException, status
from sk_common.people.models import User
from sk_common.security import hash_secret, new_secret, now_utc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.responses.models import STATUS_SUBMITTED, Answer, RankingItem, Response
from app.modules.responses.schemas import (
    AnswerIn,
    AnswerOut,
    PublicOption,
    PublicQuestion,
    PublicSurvey,
    ResponseState,
    StartResult,
)
from app.modules.surveys.models import (
    MATRIX_TYPES,
    SCALE_GENERATED,
    TEXT_LIST,
    TEXT_LIST_MAX_ROWS,
    Publishing,
    Question,
    Scale,
    Section,
    Survey,
)
from app.modules.surveys.schemas import ScaleOut, SectionOut

RICH_TEXT_TAGS = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'ul', 'ol', 'li', 'blockquote', 'a', 'h3', 'h4'}


class AnswerError(Exception):
    pass


def _bad(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, message)


# --- Публикация -----------------------------------------------------------------------------


async def open_publishing(db: AsyncSession, token: str) -> Publishing:
    """Публикация, по которой сейчас можно отвечать."""
    publishing = await db.scalar(select(Publishing).where(Publishing.public_token == token))
    if publishing is None or not publishing.is_active or not publishing.survey.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Опрос не найден или уже закрыт')
    now = now_utc()
    if publishing.opens_at and now < publishing.opens_at:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Опрос ещё не начался')
    if publishing.closes_at and now >= publishing.closes_at:
        raise HTTPException(status.HTTP_410_GONE, 'Опрос завершён')
    return publishing


async def active_questions(db: AsyncSession, survey_id: int) -> list[Question]:
    visible = select(Section.id).where(Section.survey_id == survey_id, Section.is_active.is_(True))
    rows = await db.scalars(
        select(Question)
        .where(
            Question.survey_id == survey_id,
            Question.is_active.is_(True),
            Question.section_id.is_(None) | Question.section_id.in_(visible),
        )
        .order_by(Question.order)
    )
    return list(rows)


async def public_survey(db: AsyncSession, publishing: Publishing, user: User | None) -> PublicSurvey:
    survey: Survey = publishing.survey
    requires_login = not publishing.is_anonymous and user is None
    return await survey_form(db, survey, publishing.title, publishing.is_anonymous, requires_login)


async def survey_form(
    db: AsyncSession,
    survey: Survey,
    publishing_title: str = '',
    is_anonymous: bool = True,
    requires_login: bool = False,
) -> PublicSurvey:
    result = PublicSurvey(
        publishing_title=publishing_title,
        is_anonymous=is_anonymous,
        requires_login=requires_login,
        title=survey.title,
        description=survey.description,
        intro_text=survey.intro_text,
        thank_you_text=survey.thank_you_text,
        one_question_per_page=survey.one_question_per_page,
    )
    if requires_login:
        return result
    await db.refresh(survey, ['sections'])
    questions = await active_questions(db, survey.id)
    scale_ids = {q.scale_id for q in questions if q.scale_id}
    scales = list(await db.scalars(select(Scale).where(Scale.id.in_(scale_ids or {0}))))
    sections = []
    for section in survey.sections:
        if section.is_active:
            public_section = SectionOut.model_validate(section)
            if not section.show_heading:
                public_section = public_section.model_copy(update={'title': '', 'description': ''})
            sections.append(public_section)
    return result.model_copy(
        update={
            'sections': sections,
            'questions': [
                PublicQuestion.model_validate(q).model_copy(
                    update={'options': [PublicOption.model_validate(o) for o in q.options if o.is_active]}
                )
                for q in questions
            ],
            'scales': [ScaleOut.model_validate(scale) for scale in scales],
        }
    )


# --- Прохождение ----------------------------------------------------------------------------


def _state(response: Response, token: str | None = None) -> StartResult:
    return StartResult(
        response_id=response.id,
        status=response.status,
        submitted_at=response.submitted_at,
        answers=[AnswerOut.model_validate(a) for a in response.answers],
        response_token=token,
    )


async def start_response(db: AsyncSession, publishing: Publishing, user: User | None) -> StartResult:
    """Новое прохождение. Для неанонимной публикации - продолжение своего, ключ выдаётся заново."""
    token = new_secret()
    if publishing.is_anonymous:
        response = Response(publishing_id=publishing.id, token_hash=hash_secret(token))
        db.add(response)
        await db.flush()
        await db.refresh(response, ['answers'])
        return _state(response, token)

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Войдите, чтобы пройти опрос')
    response = await db.scalar(
        select(Response).where(Response.publishing_id == publishing.id, Response.user_id == user.id).with_for_update()
    )
    if response is None:
        response = Response(publishing_id=publishing.id, user_id=user.id, token_hash=hash_secret(token))
        db.add(response)
    else:
        response.token_hash = hash_secret(token)
    await db.flush()
    await db.refresh(response, ['answers'])
    return _state(response, token)


async def response_by_token(db: AsyncSession, token: str | None, lock: bool = False) -> Response:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Нет ключа прохождения. Откройте опрос по ссылке заново.')
    query = select(Response).where(Response.token_hash == hash_secret(token))
    if lock:
        query = query.with_for_update()
    response = await db.scalar(query)
    if response is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Прохождение не найдено. Откройте опрос по ссылке заново.')
    return response


def response_state(response: Response) -> ResponseState:
    return _state(response)


async def save_answer(db: AsyncSession, response: Response, question_id: int, data: AnswerIn) -> Answer | None:
    if response.status == STATUS_SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, 'Ответы уже отправлены')
    publishing = await db.get(Publishing, response.publishing_id)
    await open_publishing(db, publishing.public_token)
    question = await db.get(Question, question_id, with_for_update={'read': True})
    section = await db.get(Section, question.section_id) if question and question.section_id else None
    if (
        question is None
        or question.survey_id != publishing.survey_id
        or not question.is_active
        or (section and not section.is_active)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Вопрос не найден')

    answer = await db.scalar(select(Answer).where(Answer.response_id == response.id, Answer.question_id == question_id))
    if answer is None:
        answer = Answer(response_id=response.id, question_id=question_id)
        db.add(answer)
        await db.flush()
    await db.refresh(answer, ['selected_options', 'ranking'])
    try:
        await _apply(db, question, answer, data)
    except AnswerError as exc:
        raise _bad(str(exc)) from exc
    response.updated_at = now_utc()
    await db.flush()
    return answer


async def _apply(db: AsyncSession, question: Question, answer: Answer, data: AnswerIn) -> None:
    for field in ('text_value', 'rich_text_value', 'number_value', 'boolean_value', 'scale_item_id', 'option_id'):
        setattr(answer, field, None)
    answer.selected_options = []
    answer.ranking = []
    answer.matrix_choices = {}
    answer.text_rows = []
    answer.is_skipped = data.is_skipped and not question.is_required
    if answer.is_skipped:
        return

    options = {o.id: o for o in question.options if o.is_active}
    kind = question.question_type
    if kind == 'text':
        answer.text_value = (data.text_value or '').strip() or None
    elif kind == TEXT_LIST:
        rows = [row for value in data.text_rows if (row := value.strip())]
        maximum = question.max_rows or TEXT_LIST_MAX_ROWS
        if len(rows) > maximum:
            raise AnswerError(f'Максимум заполненных строк: {maximum}')
        answer.text_rows = rows
    elif kind == 'rich_text':
        clean = nh3.clean(data.rich_text_value or '', tags=RICH_TEXT_TAGS).strip()
        answer.rich_text_value = clean or None
    elif kind == 'number':
        if data.number_value is not None:
            _check_range(data.number_value, question.min_number, question.max_number)
        answer.number_value = data.number_value
    elif kind == 'yes_no':
        answer.boolean_value = data.boolean_value
    elif kind == 'single_choice':
        if data.option_id is not None and data.option_id not in options:
            raise AnswerError('Такого варианта нет')
        answer.option_id = data.option_id
    elif kind in MATRIX_TYPES:
        rows = {row['id'] for row in question.matrix_rows}
        if data.matrix_choices.keys() - rows:
            raise AnswerError('Такой строки нет')
        for selected in data.matrix_choices.values():
            if set(selected) - options.keys() or len(set(selected)) != len(selected):
                raise AnswerError('Недопустимый вариант матрицы')
            if kind == 'matrix_single' and len(selected) != 1:
                raise AnswerError('Выберите один вариант в каждой строке')
        answer.matrix_choices = data.matrix_choices
    elif kind == 'multiple_choice':
        chosen = list(dict.fromkeys(data.option_ids))
        if set(chosen) - set(options):
            raise AnswerError('Такого варианта нет')
        if question.max_selections and len(chosen) > question.max_selections:
            raise AnswerError(f'Можно выбрать не больше {question.max_selections}')
        answer.selected_options = [options[i] for i in chosen]
    elif kind == 'ranking':
        ranked = data.ranking
        if len(set(ranked)) != len(ranked) or set(ranked) - set(options):
            raise AnswerError('Такого варианта нет')
        if question.max_selections and len(ranked) > question.max_selections:
            raise AnswerError(f'Можно расставить не больше {question.max_selections}')
        answer.ranking = [RankingItem(option_id=oid, rank=rank) for rank, oid in enumerate(ranked, 1)]
    elif kind == 'scale':
        await _apply_scale(db, question, answer, data)


async def _apply_scale(db: AsyncSession, question: Question, answer: Answer, data: AnswerIn) -> None:
    scale = await db.get(Scale, question.scale_id) if question.scale_id else None
    if scale is None:
        raise AnswerError('У вопроса не задана шкала')
    if scale.scale_type == SCALE_GENERATED:
        value = data.number_value
        if value is None:
            return
        _check_range(value, scale.min_value, scale.max_value)
        if not math.isclose((value - scale.min_value) % scale.step, 0):
            raise AnswerError('Значение не совпадает с делениями шкалы')
        answer.number_value = value
        return
    if data.scale_item_id is None:
        return
    item = next((i for i in scale.items if i.id == data.scale_item_id), None)
    if item is None:
        raise AnswerError('Такого значения шкалы нет')
    answer.scale_item_id = item.id
    try:
        answer.number_value = float(item.score if item.score is not None else item.value)
    except ValueError:
        answer.number_value = None


def _check_range(value: float, low: float | None, high: float | None) -> None:
    if low is not None and value < low:
        raise AnswerError(f'Значение должно быть не меньше {low:g}')
    if high is not None and value > high:
        raise AnswerError(f'Значение должно быть не больше {high:g}')


def is_answered(answer: Answer | None) -> bool:
    if answer is None or answer.is_skipped:
        return False
    return bool(
        answer.text_value
        or answer.rich_text_value
        or answer.number_value is not None
        or answer.boolean_value is not None
        or answer.scale_item_id
        or answer.option_id
        or answer.selected_options
        or answer.ranking
        or answer.matrix_choices
    )


async def submit(db: AsyncSession, response: Response) -> Publishing:
    publishing = await db.get(Publishing, response.publishing_id)
    if response.status == STATUS_SUBMITTED:
        return publishing
    await open_publishing(db, publishing.public_token)
    await db.refresh(response, ['answers'])
    by_question = {a.question_id: a for a in response.answers}
    missing = []
    row_errors = {}
    for question in await active_questions(db, publishing.survey_id):
        answer = by_question.get(question.id)
        if question.question_type == TEXT_LIST:
            count = len(answer.text_rows) if answer and not answer.is_skipped else 0
            minimum = question.min_rows or 1
            maximum = question.max_rows or TEXT_LIST_MAX_ROWS
            if (question.is_required or count) and count < minimum:
                row_errors[question.id] = f'Минимум заполненных строк: {minimum}'
            elif count > maximum:
                row_errors[question.id] = f'Максимум заполненных строк: {maximum}'
            continue
        complete = is_answered(answer)
        if question.question_type in MATRIX_TYPES:
            complete = bool(answer) and all(row['id'] in answer.matrix_choices for row in question.matrix_rows)
        if question.is_required and not complete:
            missing.append(question.id)
        elif question.min_selections and answer and not answer.is_skipped:
            # Выбор или порядок начат, но вариантов меньше минимума
            count = len(answer.selected_options) + len(answer.ranking)
            if count and count < question.min_selections:
                missing.append(question.id)
    if row_errors:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                'message': 'Проверьте число заполненных строк и обязательные вопросы',
                'question_ids': [*missing, *row_errors],
                'question_errors': row_errors,
            },
        )
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {'message': 'Ответьте на обязательные вопросы', 'question_ids': missing},
        )
    response.status = STATUS_SUBMITTED
    response.submitted_at = now_utc()
    await db.flush()
    return publishing

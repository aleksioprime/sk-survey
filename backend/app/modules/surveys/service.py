"""Конструктор опросов."""

import secrets
import string
from datetime import datetime

from fastapi import HTTPException, status
from sk_common.people.models import Person, User
from sk_common.people.service import ensure_user
from sk_common.security import now_utc
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.responses.models import STATUS_IN_PROGRESS, STATUS_SUBMITTED, Answer, Response
from app.modules.responses.service import active_questions
from app.modules.surveys.models import (
    MATRIX_TYPES,
    ROLE_EDITOR,
    ROLE_OWNER,
    SCALE_ITEMS,
    Option,
    Publishing,
    Question,
    Scale,
    ScaleItem,
    ScaleRange,
    Section,
    Survey,
    SurveyMember,
    publishing_observers,
)
from app.modules.surveys.schemas import (
    MemberOut,
    ObserverOut,
    OrderIn,
    PublishingIn,
    PublishingOut,
    PublishingPatch,
    QuestionIn,
    QuestionOut,
    ScaleIn,
    SectionIn,
    SurveyIn,
    SurveyListItem,
    SurveyOut,
    SurveyPatch,
)

TOKEN_ALPHABET = string.ascii_lowercase + string.digits


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, message)


# --- Опросы ---------------------------------------------------------------------------------


async def list_surveys(db: AsyncSession, user: User) -> list[SurveyListItem]:
    query = select(Survey, SurveyMember.role).outerjoin(
        SurveyMember, (SurveyMember.survey_id == Survey.id) & (SurveyMember.user_id == user.id)
    )
    if not user.is_superuser:
        query = query.where(SurveyMember.user_id == user.id)
    rows = (await db.execute(query.order_by(Survey.updated_at.desc()))).unique().all()
    ids = [survey.id for survey, _ in rows]
    questions = await _count_by(db, Question.survey_id, ids)
    publishings = await _count_by(db, Publishing.survey_id, ids)
    responses = dict(
        (
            await db.execute(
                select(Publishing.survey_id, func.count(Response.id))
                .join(Response, Response.publishing_id == Publishing.id)
                .where(Publishing.survey_id.in_(ids), Response.status == STATUS_SUBMITTED)
                .group_by(Publishing.survey_id)
            )
        ).all()
    )
    return [
        SurveyListItem.model_validate(survey).model_copy(
            update={
                'questions_count': questions.get(survey.id, 0),
                'publishings_count': publishings.get(survey.id, 0),
                'responses_count': responses.get(survey.id, 0),
                'role': role or 'admin',
            }
        )
        for survey, role in rows
    ]


async def _count_by(db: AsyncSession, column, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    return dict((await db.execute(select(column, func.count()).where(column.in_(ids)).group_by(column))).all())


async def survey_out(db: AsyncSession, survey: Survey, role: str | None) -> SurveyOut:
    await db.refresh(survey)
    await db.refresh(survey, ['sections', 'questions'])
    answered = await answers_by_question(db, [q.id for q in survey.questions])
    members = await db.scalars(
        select(SurveyMember)
        .where(SurveyMember.survey_id == survey.id)
        .options(joinedload(SurveyMember.user).joinedload(User.person))
        .execution_options(populate_existing=True)
    )
    return SurveyOut(
        **{
            field: getattr(survey, field)
            for field in SurveyOut.model_fields
            if field not in ('sections', 'questions', 'members', 'role')
        },
        sections=survey.sections,
        questions=[
            QuestionOut.model_validate(q).model_copy(update={'answers_count': answered.get(q.id, 0)})
            for q in survey.questions
        ],
        members=[_member_out(m) for m in members.unique()],
        role=role,
    )


def _member_out(member: SurveyMember) -> MemberOut:
    user = member.user
    return MemberOut(
        user_id=user.id,
        person_id=user.person_id,
        email=user.email,
        full_name=user.person.full_name if user.person else user.email,
        role=member.role,
    )


async def answers_by_question(db: AsyncSession, question_ids: list[int]) -> dict[int, int]:
    return await _count_by(db, Answer.question_id, question_ids)


async def _check_code(db: AsyncSession, code: str | None, survey_id: int | None = None) -> str | None:
    code = (code or '').strip() or None
    if code and await db.scalar(select(Survey.id).where(Survey.code == code, Survey.id != (survey_id or 0))):
        raise conflict('Опрос с таким кодом уже есть')
    return code


async def create_survey(db: AsyncSession, user: User, data: SurveyIn) -> Survey:
    survey = Survey(**data.model_dump(exclude={'code'}), code=await _check_code(db, data.code), created_by_id=user.id)
    survey.members = [SurveyMember(user_id=user.id, role=ROLE_OWNER)]
    db.add(survey)
    await db.flush()
    return survey


async def update_survey(db: AsyncSession, survey: Survey, data: SurveyPatch) -> None:
    changes = data.model_dump(exclude_unset=True)
    if 'code' in changes:
        changes['code'] = await _check_code(db, changes['code'], survey.id)
    for field, value in changes.items():
        setattr(survey, field, value)
    await db.flush()


async def delete_survey(db: AsyncSession, survey: Survey) -> None:
    submitted = await db.scalar(
        select(func.count(Response.id))
        .join(Publishing, Publishing.id == Response.publishing_id)
        .where(Publishing.survey_id == survey.id, Response.status == STATUS_SUBMITTED)
    )
    if submitted:
        raise conflict('По опросу уже есть ответы. Выключите его вместо удаления.')
    await db.delete(survey)
    await db.flush()


async def copy_survey(db: AsyncSession, source: Survey, user: User) -> Survey:
    """Копия опроса со структурой, без публикаций и ответов (например, на новый учебный год)."""
    await db.refresh(source, ['sections', 'questions'])
    survey = Survey(
        title=f'{source.title} (копия)',
        description=source.description,
        intro_text=source.intro_text,
        thank_you_text=source.thank_you_text,
        is_active=source.is_active,
        is_anonymous=source.is_anonymous,
        created_by_id=user.id,
    )
    survey.members = [SurveyMember(user_id=user.id, role=ROLE_OWNER)]
    db.add(survey)
    await db.flush()
    sections = {}
    for section in source.sections:
        sections[section.id] = Section(
            survey_id=survey.id,
            title=section.title,
            description=section.description,
            order=section.order,
            is_active=section.is_active,
        )
        db.add(sections[section.id])
    await db.flush()
    for question in source.questions:
        copy = Question(
            survey_id=survey.id,
            section_id=sections[question.section_id].id if question.section_id in sections else None,
            **{
                field: getattr(question, field)
                for field in (
                    'text',
                    'description',
                    'question_type',
                    'order',
                    'is_required',
                    'is_active',
                    'scale_id',
                    'min_selections',
                    'max_selections',
                    'min_rows',
                    'max_rows',
                    'min_number',
                    'max_number',
                    'is_options_shuffled',
                    'matrix_rows',
                )
            },
        )
        copy.options = [
            Option(
                title=o.title,
                description=o.description,
                value=o.value,
                score=o.score,
                exclude_from_base=o.exclude_from_base,
                order=o.order,
                is_active=o.is_active,
            )
            for o in question.options
        ]
        copy.ranges = [
            ScaleRange(title=r.title, from_value=r.from_value, to_value=r.to_value, order=r.order)
            for r in question.ranges
        ]
        db.add(copy)
    await db.flush()
    return survey


async def set_editors(db: AsyncSession, survey: Survey, person_ids: list[int]) -> None:
    await db.refresh(survey, ['members'])
    owners = [m for m in survey.members if m.role == ROLE_OWNER]
    users = await users_for_persons(db, person_ids)
    owner_ids = {m.user_id for m in owners}
    if any(user.id in owner_ids for user in users):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Владелец уже может редактировать опрос')
    current_editors = {member.user_id: member for member in survey.members if member.role == ROLE_EDITOR}
    survey.members = owners + [
        current_editors.get(user_id) or SurveyMember(user_id=user_id, role=ROLE_EDITOR)
        for user_id in dict.fromkeys(user.id for user in users)
    ]
    await db.flush()


async def users_for_persons(db: AsyncSession, person_ids: list[int]) -> list[User]:
    """Учётные записи для сотрудников из справочника. Кто ещё ни разу не входил, получает запись сейчас."""
    persons = list(await db.scalars(select(Person).where(Person.id.in_(person_ids or [0]))))
    if len(persons) != len(set(person_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Человек не найден в справочнике')
    users = []
    for person in persons:
        if not person.email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'У {person.full_name} нет email — войти он не сможет')
        users.append(await ensure_user(db, person, person.email))
    return users


# --- Разделы и вопросы ----------------------------------------------------------------------


async def _next_order(db: AsyncSession, column, survey_column, survey_id: int) -> int:
    return (await db.scalar(select(func.max(column)).where(survey_column == survey_id)) or 0) + 1


async def add_section(db: AsyncSession, survey: Survey, data: SectionIn) -> Section:
    order = await _next_order(db, Section.order, Section.survey_id, survey.id)
    section = Section(survey_id=survey.id, order=order, **data.model_dump())
    db.add(section)
    await db.flush()
    return section


async def get_section(db: AsyncSession, section_id: int) -> Section:
    section = await db.get(Section, section_id)
    if section is None:
        raise not_found('Раздел не найден')
    return section


async def update_section(db: AsyncSession, section: Section, data: SectionIn) -> None:
    for field, value in data.model_dump().items():
        setattr(section, field, value)
    await db.flush()


async def get_question(db: AsyncSession, question_id: int, lock: bool = False) -> Question:
    question = await db.get(Question, question_id, with_for_update=lock)
    if question is None:
        raise not_found('Вопрос не найден')
    return question


async def _check_question_refs(db: AsyncSession, survey_id: int, data: QuestionIn) -> None:
    if data.section_id is not None:
        section = await db.get(Section, data.section_id)
        if section is None or section.survey_id != survey_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Раздел из другого опроса')
    if data.scale_id is not None and await db.get(Scale, data.scale_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Шкала не найдена')


async def add_question(db: AsyncSession, survey: Survey, data: QuestionIn) -> Question:
    await _check_question_refs(db, survey.id, data)
    order = await _next_order(db, Question.order, Question.survey_id, survey.id)
    question = Question(survey_id=survey.id, order=order, **data.model_dump(exclude={'options', 'ranges'}))
    question.options = [
        Option(order=index, **item.model_dump(exclude={'id'})) for index, item in enumerate(data.options, 1)
    ]
    question.ranges = [
        ScaleRange(order=index, **item.model_dump(exclude={'id'})) for index, item in enumerate(data.ranges, 1)
    ]
    db.add(question)
    await db.flush()
    return question


async def update_question(db: AsyncSession, question: Question, data: QuestionIn) -> None:
    """Варианты обновляются по id; новые создаются; убранные удаляются, а выбранные в ответах — выключаются."""
    await _check_question_refs(db, question.survey_id, data)
    answered = await answers_by_question(db, [question.id])
    if answered and data.question_type != question.question_type:
        raise conflict('На вопрос уже отвечали — тип ответа менять нельзя')
    if answered and question.question_type in MATRIX_TYPES:
        current = [(o.id, o.title, o.is_active) for o in question.options]
        incoming = [(o.id, o.title, o.is_active) for o in data.options]
        rows = [row.model_dump() for row in data.matrix_rows]
        if current != incoming or question.matrix_rows != rows:
            raise conflict('На матрицу уже отвечали — строки и варианты менять нельзя')
    for field, value in data.model_dump(exclude={'options', 'ranges'}).items():
        setattr(question, field, value)

    await db.refresh(question, ['options', 'ranges'])
    existing = {option.id: option for option in question.options}
    kept = []
    for index, item in enumerate(data.options, 1):
        option = existing.pop(item.id, None) if item.id else None
        if option is None:
            option = Option(question_id=question.id)
        for field, value in item.model_dump(exclude={'id'}).items():
            setattr(option, field, value)
        option.order = index
        kept.append(option)
    used = await _used_options(db, list(existing))
    for option in existing.values():
        if option.id in used:
            option.is_active = False
            option.order = len(kept) + 1
            kept.append(option)
    question.options = kept
    question.ranges = [
        ScaleRange(order=index, **item.model_dump(exclude={'id'})) for index, item in enumerate(data.ranges, 1)
    ]
    await db.flush()


async def _used_options(db: AsyncSession, option_ids: list[int]) -> set[int]:
    from app.modules.responses.models import RankingItem, answer_options

    if not option_ids:
        return set()
    used = set(await db.scalars(select(Answer.option_id).where(Answer.option_id.in_(option_ids))))
    used |= set(await db.scalars(select(answer_options.c.option_id).where(answer_options.c.option_id.in_(option_ids))))
    used |= set(await db.scalars(select(RankingItem.option_id).where(RankingItem.option_id.in_(option_ids))))
    return used


async def delete_question(db: AsyncSession, question: Question) -> None:
    if await answers_by_question(db, [question.id]):
        raise conflict('На вопрос уже отвечали. Выключите его вместо удаления.')
    await db.delete(question)
    await db.flush()


async def reorder(db: AsyncSession, survey: Survey, data: OrderIn) -> None:
    await db.refresh(survey, ['sections', 'questions'])
    sections = {s.id: s for s in survey.sections}
    questions = {q.id: q for q in survey.questions}
    if set(data.sections) - set(sections) or {q.id for q in data.questions} - set(questions):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Раздел или вопрос из другого опроса')
    for index, section_id in enumerate(data.sections, 1):
        sections[section_id].order = index
    for index, place in enumerate(data.questions, 1):
        if place.section_id is not None and place.section_id not in sections:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Раздел из другого опроса')
        questions[place.id].order = index
        questions[place.id].section_id = place.section_id
    await db.flush()


# --- Шкалы ----------------------------------------------------------------------------------


async def save_scale(db: AsyncSession, data: ScaleIn, scale: Scale | None = None) -> Scale:
    if scale is None:
        scale = Scale()
        db.add(scale)
    else:
        await db.refresh(scale, ['items'])
    for field, value in data.model_dump(exclude={'items'}).items():
        setattr(scale, field, value)
    existing = {item.id: item for item in scale.items}
    items = []
    if data.scale_type == SCALE_ITEMS:
        for index, payload in enumerate(data.items, 1):
            item = existing.pop(payload.id, None) if payload.id else None
            item = item or ScaleItem()
            for field, value in payload.model_dump(exclude={'id'}).items():
                setattr(item, field, value)
            item.order = index
            items.append(item)
    scale.items = items
    await db.flush()
    return scale


# --- Публикации -----------------------------------------------------------------------------


async def new_public_token(db: AsyncSession) -> str:
    while True:
        token = ''.join(secrets.choice(TOKEN_ALPHABET) for _ in range(10))
        if not await db.scalar(select(Publishing.id).where(Publishing.public_token == token)):
            return token


def _check_period(opens_at: datetime | None, closes_at: datetime | None) -> None:
    if any(value and value.utcoffset() is None for value in (opens_at, closes_at)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Укажите часовой пояс для дат публикации')
    if opens_at and closes_at and closes_at <= opens_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Закрытие должно быть позже открытия')


async def _check_publishable(db: AsyncSession, survey_id: int) -> None:
    questions = await active_questions(db, survey_id)
    if not questions:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Добавьте хотя бы один доступный вопрос')
    for question in questions:
        if (
            question.question_type in (*MATRIX_TYPES, 'single_choice', 'multiple_choice', 'ranking')
            and sum(option.is_active for option in question.options) < 2
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'Мало активных вариантов: {question.text}')
        if question.question_type == 'scale' and not question.scale_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f'Не задана шкала: {question.text}')


async def create_publishing(db: AsyncSession, survey: Survey, user: User, data: PublishingIn) -> Publishing:
    _check_period(data.opens_at, data.closes_at)
    if data.is_active:
        await _check_publishable(db, survey.id)
    publishing = Publishing(
        survey_id=survey.id,
        public_token=await new_public_token(db),
        created_by_id=user.id,
        **data.model_dump(exclude={'observer_person_ids'}),
    )
    publishing.observers = await users_for_persons(db, data.observer_person_ids)
    db.add(publishing)
    await db.flush()
    return publishing


async def update_publishing(db: AsyncSession, publishing: Publishing, data: PublishingPatch) -> None:
    changes = data.model_dump(exclude_unset=True)
    if {'opens_at', 'closes_at'} & changes.keys():
        _check_period(changes.get('opens_at', publishing.opens_at), changes.get('closes_at', publishing.closes_at))
    if not publishing.is_active and changes.get('is_active'):
        await _check_publishable(db, publishing.survey_id)
    if (person_ids := changes.pop('observer_person_ids', None)) is not None:
        publishing.observers = await users_for_persons(db, person_ids)
    anonymity_changed = changes.get('is_anonymous') is not None and changes['is_anonymous'] != publishing.is_anonymous
    if anonymity_changed and await db.scalar(
        select(func.count(Response.id)).where(Response.publishing_id == publishing.id)
    ):
        raise conflict('По публикации уже есть ответы — анонимность менять нельзя')
    for field, value in changes.items():
        setattr(publishing, field, value)
    await db.flush()


async def delete_publishing(db: AsyncSession, publishing: Publishing) -> None:
    if await db.scalar(
        select(func.count(Response.id)).where(
            Response.publishing_id == publishing.id, Response.status == STATUS_SUBMITTED
        )
    ):
        raise conflict('По публикации уже есть ответы. Выключите её вместо удаления.')
    await db.delete(publishing)
    await db.flush()


def publishing_status(publishing: Publishing) -> str:
    now = now_utc()
    if not publishing.is_active or not publishing.survey.is_active:
        return 'closed'
    if publishing.closes_at and publishing.closes_at <= now:
        return 'closed'
    if publishing.opens_at and publishing.opens_at > now:
        return 'scheduled'
    return 'open'


async def publishings_out(
    db: AsyncSession, publishings: list[Publishing], editable: set[int] | None = None
) -> list[PublishingOut]:
    ids = [p.id for p in publishings]
    counts: dict[tuple[int, str], int] = {}
    if ids:
        rows = await db.execute(
            select(Response.publishing_id, Response.status, func.count())
            .where(Response.publishing_id.in_(ids))
            .group_by(Response.publishing_id, Response.status)
        )
        counts = {(pid, st): n for pid, st, n in rows.all()}
    result = []
    for p in publishings:
        result.append(
            PublishingOut(
                id=p.id,
                survey_id=p.survey_id,
                survey_title=p.survey.title,
                title=p.title,
                public_token=p.public_token,
                is_active=p.is_active,
                is_anonymous=p.is_anonymous,
                opens_at=p.opens_at,
                closes_at=p.closes_at,
                created_at=p.created_at,
                observers=[
                    ObserverOut(
                        user_id=u.id,
                        person_id=u.person_id,
                        email=u.email,
                        full_name=u.person.full_name if u.person else u.email,
                    )
                    for u in p.observers
                ],
                submitted_count=counts.get((p.id, STATUS_SUBMITTED), 0),
                in_progress_count=counts.get((p.id, STATUS_IN_PROGRESS), 0),
                status=publishing_status(p),
                can_edit=editable is None or p.survey_id in editable,
            )
        )
    return result


async def cabinet_publishings(db: AsyncSession, user: User) -> list[PublishingOut]:
    """Публикации в кабинете: опросы, которые человек ведёт, и те, где он наблюдатель."""
    member_surveys = set(await db.scalars(select(SurveyMember.survey_id).where(SurveyMember.user_id == user.id)))
    query = select(Publishing)
    if not user.is_superuser:
        observed = select(publishing_observers.c.publishing_id).where(publishing_observers.c.user_id == user.id)
        query = query.where(Publishing.survey_id.in_(member_surveys or {0}) | Publishing.id.in_(observed))
    rows = list((await db.scalars(query.order_by(Publishing.created_at.desc()))).unique())
    editable = None if user.is_superuser else member_surveys
    return await publishings_out(db, rows, editable)

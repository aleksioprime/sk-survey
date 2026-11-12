from fastapi import APIRouter, HTTPException, Response, status
from sk_common.audit import record
from sk_common.deps import CurrentUser, Db
from sqlalchemy import select

from app.modules.surveys import service
from app.modules.surveys.models import Publishing, Scale
from app.modules.surveys.permissions import (
    can_create_surveys,
    editable_survey,
    require_owner,
    survey_role,
    viewable_publishing,
)
from app.modules.surveys.schemas import (
    MembersIn,
    OrderIn,
    PublishingIn,
    PublishingOut,
    PublishingPatch,
    QuestionIn,
    QuestionOut,
    ScaleIn,
    ScaleOut,
    SectionIn,
    SectionOut,
    SurveyAccessIn,
    SurveyAccessOut,
    SurveyIn,
    SurveyListItem,
    SurveyOut,
    SurveyPatch,
)

router = APIRouter(prefix='/v1', tags=['surveys'])


def _require_creator(user) -> None:
    if not can_create_surveys(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Опросы создают сотрудники гимназии')


# --- Опросы ---------------------------------------------------------------------------------


@router.get('/surveys', response_model=list[SurveyListItem], summary='Мои опросы')
async def list_surveys(db: Db, user: CurrentUser, include_observed: bool = False) -> list[SurveyListItem]:
    return await service.list_surveys(db, user, include_observed=include_observed)


@router.post('/surveys', response_model=SurveyOut, status_code=201, summary='Создать опрос')
async def create_survey(payload: SurveyIn, db: Db, user: CurrentUser) -> SurveyOut:
    _require_creator(user)
    survey = await service.create_survey(db, user, payload)
    record(db, 'survey.create', 'survey', survey.id, user.id)
    await db.commit()
    return await service.survey_out(db, survey, 'owner')


@router.get('/surveys/{survey_id}', response_model=SurveyOut, summary='Опрос со структурой')
async def get_survey(survey_id: int, db: Db, user: CurrentUser) -> SurveyOut:
    survey, role = await editable_survey(db, survey_id, user)
    return await service.survey_out(db, survey, role)


@router.patch('/surveys/{survey_id}', response_model=SurveyOut, summary='Изменить опрос')
async def update_survey(survey_id: int, payload: SurveyPatch, db: Db, user: CurrentUser) -> SurveyOut:
    survey, role = await editable_survey(db, survey_id, user)
    await service.update_survey(db, survey, payload)
    record(db, 'survey.update', 'survey', survey.id, user.id, **payload.model_dump(exclude_unset=True, mode='json'))
    await db.commit()
    return await service.survey_out(db, survey, role)


@router.delete('/surveys/{survey_id}', status_code=204, summary='Удалить опрос без ответов')
async def delete_survey(survey_id: int, db: Db, user: CurrentUser) -> Response:
    survey, role = await editable_survey(db, survey_id, user, lock=True)
    require_owner(role)
    await service.delete_survey(db, survey)
    record(db, 'survey.delete', 'survey', survey_id, user.id)
    await db.commit()
    return Response(status_code=204)


@router.post('/surveys/{survey_id}/copy', response_model=SurveyOut, status_code=201, summary='Копия опроса')
async def copy_survey(survey_id: int, db: Db, user: CurrentUser) -> SurveyOut:
    _require_creator(user)
    source, _ = await editable_survey(db, survey_id, user)
    survey = await service.copy_survey(db, source, user)
    record(db, 'survey.copy', 'survey', survey.id, user.id, source_id=survey_id)
    await db.commit()
    return await service.survey_out(db, survey, 'owner')


@router.put('/surveys/{survey_id}/members', response_model=SurveyOut, summary='Редакторы опроса')
async def set_members(survey_id: int, payload: MembersIn, db: Db, user: CurrentUser) -> SurveyOut:
    survey, role = await editable_survey(db, survey_id, user, lock=True)
    require_owner(role)
    await service.set_editors(db, survey, payload.editor_person_ids)
    record(db, 'survey.members', 'survey', survey.id, user.id, editors=payload.editor_person_ids)
    await db.commit()
    return await service.survey_out(db, survey, role)


@router.put('/surveys/{survey_id}/access', response_model=SurveyAccessOut, summary='Доступ к опросу')
async def set_survey_access(survey_id: int, payload: SurveyAccessIn, db: Db, user: CurrentUser) -> SurveyAccessOut:
    survey, role = await editable_survey(db, survey_id, user, lock=True)
    require_owner(role)
    await service.set_survey_access(db, survey, payload.members)
    members = await service.survey_members_out(db, survey.id)
    record(
        db,
        'survey.access',
        'survey',
        survey.id,
        user.id,
        members=[{'user_id': member.user_id, 'role': member.role} for member in members],
    )
    role = await survey_role(db, survey.id, user)
    await db.commit()
    return SurveyAccessOut(members=members, role=role)


@router.put('/surveys/{survey_id}/order', response_model=SurveyOut, summary='Порядок разделов и вопросов')
async def reorder(survey_id: int, payload: OrderIn, db: Db, user: CurrentUser) -> SurveyOut:
    survey, role = await editable_survey(db, survey_id, user)
    await service.reorder(db, survey, payload)
    await db.commit()
    return await service.survey_out(db, survey, role)


# --- Разделы --------------------------------------------------------------------------------


@router.post('/surveys/{survey_id}/sections', response_model=SectionOut, status_code=201, summary='Добавить раздел')
async def add_section(survey_id: int, payload: SectionIn, db: Db, user: CurrentUser) -> SectionOut:
    survey, _ = await editable_survey(db, survey_id, user)
    section = await service.add_section(db, survey, payload)
    await db.commit()
    return SectionOut.model_validate(section)


@router.patch('/sections/{section_id}', response_model=SectionOut, summary='Изменить раздел')
async def update_section(section_id: int, payload: SectionIn, db: Db, user: CurrentUser) -> SectionOut:
    section = await service.get_section(db, section_id)
    await editable_survey(db, section.survey_id, user)
    await service.update_section(db, section, payload)
    await db.commit()
    return SectionOut.model_validate(section)


@router.delete('/sections/{section_id}', status_code=204, summary='Удалить раздел (вопросы остаются без раздела)')
async def delete_section(section_id: int, db: Db, user: CurrentUser) -> Response:
    section = await service.get_section(db, section_id)
    await editable_survey(db, section.survey_id, user)
    await db.delete(section)
    await db.commit()
    return Response(status_code=204)


# --- Вопросы --------------------------------------------------------------------------------


@router.post('/surveys/{survey_id}/questions', response_model=QuestionOut, status_code=201, summary='Добавить вопрос')
async def add_question(survey_id: int, payload: QuestionIn, db: Db, user: CurrentUser) -> QuestionOut:
    survey, _ = await editable_survey(db, survey_id, user)
    question = await service.add_question(db, survey, payload)
    await db.commit()
    await db.refresh(question, ['options', 'ranges'])
    return QuestionOut.model_validate(question)


@router.put('/questions/{question_id}', response_model=QuestionOut, summary='Изменить вопрос')
async def update_question(question_id: int, payload: QuestionIn, db: Db, user: CurrentUser) -> QuestionOut:
    question = await service.get_question(db, question_id, lock=True)
    await editable_survey(db, question.survey_id, user)
    await service.update_question(db, question, payload)
    await db.commit()
    await db.refresh(question, ['options', 'ranges'])
    answered = await service.answers_by_question(db, [question.id])
    return QuestionOut.model_validate(question).model_copy(update={'answers_count': answered.get(question.id, 0)})


@router.delete('/questions/{question_id}', status_code=204, summary='Удалить вопрос без ответов')
async def delete_question(question_id: int, db: Db, user: CurrentUser) -> Response:
    question = await service.get_question(db, question_id, lock=True)
    await editable_survey(db, question.survey_id, user)
    await service.delete_question(db, question)
    await db.commit()
    return Response(status_code=204)


# --- Шкалы ----------------------------------------------------------------------------------


@router.get('/scales', response_model=list[ScaleOut], summary='Шкалы')
async def list_scales(
    db: Db, user: CurrentUser, include_usage: bool = False, survey_id: int | None = None
) -> list[ScaleOut]:
    if include_usage or survey_id is None:
        _require_creator(user)
    else:
        await editable_survey(db, survey_id, user)
    scales = await db.scalars(select(Scale).order_by(Scale.title))
    usage = await service.scale_usage(db, user) if include_usage else {}
    return [ScaleOut.model_validate(scale).model_copy(update={'used_in': usage.get(scale.id, [])}) for scale in scales]


@router.post('/scales', response_model=ScaleOut, status_code=201, summary='Создать шкалу')
async def create_scale(payload: ScaleIn, db: Db, user: CurrentUser) -> Scale:
    _require_creator(user)
    scale = await service.save_scale(db, payload)
    record(db, 'scale.create', 'scale', scale.id, user.id)
    await db.commit()
    await db.refresh(scale, ['items'])
    return scale


@router.put('/scales/{scale_id}', response_model=ScaleOut, summary='Изменить шкалу')
async def update_scale(scale_id: int, payload: ScaleIn, db: Db, user: CurrentUser) -> Scale:
    _require_creator(user)
    scale = await db.get(Scale, scale_id)
    if scale is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Шкала не найдена')
    await service.save_scale(db, payload, scale)
    record(db, 'scale.update', 'scale', scale.id, user.id)
    await db.commit()
    await db.refresh(scale, ['items'])
    return scale


# --- Публикации -----------------------------------------------------------------------------


@router.get('/publishings', response_model=list[PublishingOut], summary='Публикации в кабинете')
async def cabinet_publishings(db: Db, user: CurrentUser, survey_id: int | None = None) -> list[PublishingOut]:
    return await service.cabinet_publishings(db, user, survey_id)


@router.get('/surveys/{survey_id}/publishings', response_model=list[PublishingOut], summary='Публикации опроса')
async def survey_publishings(survey_id: int, db: Db, user: CurrentUser) -> list[PublishingOut]:
    await editable_survey(db, survey_id, user)
    rows = await db.scalars(
        select(Publishing).where(Publishing.survey_id == survey_id).order_by(Publishing.created_at.desc())
    )
    return await service.publishings_out(db, list(rows.unique()))


@router.post(
    '/surveys/{survey_id}/publishings', response_model=PublishingOut, status_code=201, summary='Опубликовать опрос'
)
async def create_publishing(survey_id: int, payload: PublishingIn, db: Db, user: CurrentUser) -> PublishingOut:
    survey, _ = await editable_survey(db, survey_id, user)
    publishing = await service.create_publishing(db, survey, user, payload)
    record(db, 'publishing.create', 'publishing', publishing.id, user.id, survey_id=survey_id)
    await db.commit()
    publishing = await db.get(Publishing, publishing.id, populate_existing=True)
    return (await service.publishings_out(db, [publishing]))[0]


@router.get('/publishings/{publishing_id}', response_model=PublishingOut, summary='Публикация')
async def get_publishing(publishing_id: int, db: Db, user: CurrentUser) -> PublishingOut:
    publishing, can_edit = await viewable_publishing(db, publishing_id, user)
    out = (await service.publishings_out(db, [publishing]))[0]
    return out.model_copy(update={'can_edit': can_edit})


@router.patch('/publishings/{publishing_id}', response_model=PublishingOut, summary='Изменить публикацию')
async def update_publishing(publishing_id: int, payload: PublishingPatch, db: Db, user: CurrentUser) -> PublishingOut:
    publishing = await _editable_publishing(db, publishing_id, user)
    await service.update_publishing(db, publishing, payload)
    record(
        db,
        'publishing.update',
        'publishing',
        publishing.id,
        user.id,
        **payload.model_dump(exclude_unset=True, mode='json'),
    )
    await db.commit()
    publishing = await db.get(Publishing, publishing.id, populate_existing=True)
    return (await service.publishings_out(db, [publishing]))[0]


@router.delete('/publishings/{publishing_id}', status_code=204, summary='Удалить публикацию без ответов')
async def delete_publishing(publishing_id: int, db: Db, user: CurrentUser) -> Response:
    publishing = await _editable_publishing(db, publishing_id, user)
    await service.delete_publishing(db, publishing)
    record(db, 'publishing.delete', 'publishing', publishing_id, user.id)
    await db.commit()
    return Response(status_code=204)


async def _editable_publishing(db, publishing_id: int, user) -> Publishing:
    publishing = await db.get(Publishing, publishing_id)
    if publishing is None or not await survey_role(db, publishing.survey_id, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Публикация не найдена')
    return publishing

"""Кто что может: создавать опросы - сотрудники и администраторы; править - участники опроса;
смотреть результаты - участники опроса и наблюдатели публикации."""

from fastapi import HTTPException, status
from sk_common.people.models import User
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surveys.models import ROLE_EDITOR, Publishing, Survey, SurveyMember, publishing_observers


def can_create_surveys(user: User) -> bool:
    return user.is_superuser or bool(user.person and user.person.is_employee)


async def survey_role(db: AsyncSession, survey_id: int, user: User) -> str | None:
    if user.is_superuser:
        return ROLE_EDITOR
    member_id = await db.scalar(
        select(SurveyMember.user_id).where(SurveyMember.survey_id == survey_id, SurveyMember.user_id == user.id)
    )
    return ROLE_EDITOR if member_id is not None else None


async def editable_survey(db: AsyncSession, survey_id: int, user: User, *, lock: bool = False) -> tuple[Survey, str]:
    survey = await db.get(Survey, survey_id, with_for_update=lock)
    role = await survey_role(db, survey_id, user) if survey else None
    if survey is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Опрос не найден')
    return survey, role


async def is_observer(db: AsyncSession, publishing_id: int, user: User) -> bool:
    return bool(
        await db.scalar(
            select(
                exists().where(
                    publishing_observers.c.publishing_id == publishing_id, publishing_observers.c.user_id == user.id
                )
            )
        )
    )


async def viewable_publishing(db: AsyncSession, publishing_id: int, user: User) -> tuple[Publishing, bool]:
    """Публикация, результаты которой пользователь может смотреть, и может ли он её менять."""
    publishing = await db.get(Publishing, publishing_id)
    if publishing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Публикация не найдена')
    if await survey_role(db, publishing.survey_id, user):
        return publishing, True
    if await is_observer(db, publishing_id, user):
        return publishing, False
    raise HTTPException(status.HTTP_404_NOT_FOUND, 'Публикация не найдена')

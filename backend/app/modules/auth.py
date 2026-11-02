"""Вход — из sk_common. В ответе /me — может ли человек создавать опросы."""

from fastapi import Request
from sk_common.auth.router import create_auth_router
from sk_common.auth.schemas import Me
from sk_common.people.models import User
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.surveys.permissions import can_create_surveys


class SurveyMe(Me):
    can_create_surveys: bool = False


async def _me_extra(db: AsyncSession, request: Request, user: User) -> dict:
    return {'can_create_surveys': can_create_surveys(user)}


router = create_auth_router(me_model=SurveyMe, me_extra=_me_extra)

"""
Публичные роутеры — доступны без авторизации.
"""

from fastapi import APIRouter

from src.routes.v1.public.surveys import router as surveys_router

router = APIRouter()
router.include_router(surveys_router, prefix='/surveys')

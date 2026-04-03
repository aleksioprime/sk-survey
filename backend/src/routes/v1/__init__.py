"""
Роутеры API v1.
"""

from fastapi import APIRouter

from src.routes.v1.public import router as public_router

router = APIRouter()

# Публичные эндпоинты (анонимное прохождение опросов)
router.include_router(public_router, prefix='/public', tags=['public'])

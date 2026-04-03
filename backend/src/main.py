"""
Точка входа FastAPI-приложения.

BFF (Backend for Frontend) — промежуточный сервер между Vue.js фронтендом
и NocoBase. Хранит API-ключ, агрегирует данные опросов в один запрос,
принимает и сохраняет ответы респондентов.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from src.core.config import settings
from src.core.logging import RequestLoggingMiddleware
from src.routes.v1 import router

app = FastAPI(
    version='0.1.0',
    title=settings.project_name,
    description=settings.project_description,
    docs_url='/api/openapi',
    openapi_url='/api/openapi.json',
    default_response_class=ORJSONResponse,
)

# Middleware: логирование запросов и CORS
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/health')
async def healthcheck():
    """Проверка доступности сервиса."""
    return {'status': 'ok'}


# Подключение роутеров API v1
app.include_router(router, prefix=settings.api_prefix)

"""
Асинхронный HTTP-клиент для работы с NocoBase REST API.

Все запросы к NocoBase проходят через этот модуль. Клиент автоматически
добавляет заголовок авторизации (API_KEY) и сериализует фильтры в формат JSON,
который ожидает NocoBase.
"""

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from src.core.config import settings

logger = logging.getLogger('sk_survey')


class NocoBaseClient:
    """Асинхронный клиент к NocoBase REST API.

    Оборачивает httpx и предоставляет CRUD-методы для работы с коллекциями
    NocoBase. Авторизация через API-ключ из настроек приложения.
    """

    def _serialize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Сериализовать вложенные объекты (filter и др.) в JSON-строки.

        NocoBase ожидает параметр `filter` как JSON-строку в query string,
        а не как вложенный Python-dict. httpx при передаче dict в params
        вызывает str(), что даёт невалидный формат с одинарными кавычками
        и Python-литералами (True/False вместо true/false).
        """
        serialized = {}
        for key, value in params.items():
            if isinstance(value, (dict, list)):
                serialized[key] = json.dumps(value)
            else:
                serialized[key] = value
        return serialized

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: Any = None,
    ) -> Any:
        """Выполнить HTTP-запрос к NocoBase API.

        Args:
            method: HTTP-метод (GET, POST, PATCH и т.д.)
            path: Путь эндпоинта (например, '/surveys:list')
            params: Query-параметры запроса
            json_payload: Тело запроса (JSON)

        Returns:
            Данные из поля 'data' ответа NocoBase или весь ответ целиком.

        Raises:
            HTTPException: если NocoBase вернул HTTP-ошибку (>= 400)
        """
        headers = {
            'Authorization': f'Bearer {settings.api_key}',
            'Content-Type': 'application/json',
        }

        # Сериализуем вложенные объекты (filter) в JSON-строки
        safe_params = self._serialize_params(params) if params else None

        async with httpx.AsyncClient(
            base_url=settings.nocobase_api_url,
            timeout=settings.nocobase_timeout,
            headers=headers,
            trust_env=False,  # Игнорируем системные прокси (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY)
        ) as client:
            response = await client.request(
                method,
                path,
                params=safe_params,
                json=json_payload,
            )

        if response.status_code >= 400:
            logger.error('NocoBase %s %s → %s: %s', method, path, response.status_code, response.text)
            raise HTTPException(
                status_code=response.status_code,
                detail=f'NocoBase error: {response.text}',
            )

        data = response.json()
        return data.get('data', data)

    async def list(self, collection: str, **params) -> list[dict]:
        """Получить список записей коллекции."""
        return await self._request('GET', f'/{collection}:list', params=params)

    async def get(self, collection: str, filter_by: dict | None = None, **params) -> dict | None:
        """Получить одну запись коллекции по фильтру. Возвращает первый элемент или None."""
        request_params = {**params}
        if filter_by:
            request_params['filter'] = filter_by
        result = await self._request('GET', f'/{collection}:list', params=request_params)
        # NocoBase :list возвращает массив записей — берём первую
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        if isinstance(result, dict) and 'data' in result:
            items = result['data']
            return items[0] if items else None
        return result if isinstance(result, dict) else None

    async def get_by_id(self, collection: str, record_id: int | str, **params) -> dict:
        """Получить запись по ID (filterByTk)."""
        return await self._request('GET', f'/{collection}:get', params={'filterByTk': record_id, **params})

    async def create(self, collection: str, data: dict) -> dict:
        """Создать новую запись в коллекции."""
        return await self._request('POST', f'/{collection}:create', json_payload=data)

    async def update(self, collection: str, record_id: int | str, data: dict) -> dict:
        """Обновить запись по ID."""
        return await self._request(
            'POST',
            f'/{collection}:update',
            params={'filterByTk': record_id},
            json_payload=data,
        )


nocobase = NocoBaseClient()

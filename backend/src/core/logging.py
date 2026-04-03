"""
Middleware для логирования HTTP-запросов.

Логирует метод, путь, статус-код и время выполнения каждого запроса.
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger('sk_survey')
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логирует каждый входящий HTTP-запрос с временем выполнения."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            '%s %s → %s (%.0f ms)',
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

"""
Конфигурация приложения.

Настройки загружаются из переменных окружения (или .env файла).
Автоматически маппятся через pydantic-settings по alias полей.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения — загружаются из переменных окружения."""

    project_name: str = Field(alias='PROJECT_NAME', default='SK Survey API')
    project_description: str = Field(
        alias='PROJECT_DESCRIPTION',
        default='Backend for Frontend — промежуточный сервер для SK Survey',
    )

    # Сетевые настройки
    default_host: str = Field(alias='HOST', default='0.0.0.0')
    default_port: int = Field(alias='PORT', default=8000)
    api_prefix: str = '/api/v1'

    # Подключение к NocoBase (внешний headless CMS)
    nocobase_url: str = Field(alias='NOCOBASE_URL', default='https://flow.skeducator.ru')
    api_key: str = Field(alias='API_KEY', default='')  # API-ключ для авторизации в NocoBase
    nocobase_timeout: float = Field(alias='NOCOBASE_TIMEOUT', default=30.0)

    # CORS — разрешённые источники (через запятую)
    cors_allow_origins_str: str = Field(
        alias='CORS_ALLOW_ORIGINS',
        default='http://localhost:3000,http://127.0.0.1:3000',
    )

    @property
    def cors_allow_origins(self) -> list[str]:
        """Разобрать строку CORS_ALLOW_ORIGINS в список."""
        return [origin.strip() for origin in self.cors_allow_origins_str.split(',')]

    @property
    def nocobase_api_url(self) -> str:
        """Полный базовый URL API NocoBase."""
        return f'{self.nocobase_url}/api'


settings = Settings()

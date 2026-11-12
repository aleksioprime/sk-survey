import sk_common
from sk_common.config import AuthSettings, DatabaseSettings, ServiceSettings, SmtpSettings


class SurveyDatabaseSettings(DatabaseSettings):
    user: str = 'sk_survey'
    password: str = 'sk_survey'
    name: str = 'sk_survey'


class SurveySmtpSettings(SmtpSettings):
    sender: str = 'SK Survey <skolstream@yandex.ru>'


class SurveyAuthSettings(AuthSettings):
    access_cookie: str = 'sks_access'
    refresh_cookie: str = 'sks_refresh'


class Settings(ServiceSettings):
    """Общие поля (БД, Redis, почта, SkolStream, вход) - в sk_common.config.ServiceSettings."""

    project_name: str = 'SK Survey'
    brand_color: str = '#0f766e'
    app_url: str = 'http://localhost:8601'
    cors_origins: list[str] = ['http://localhost:8601']
    # Сколько новых прохождений можно начать с одного IP за час (защита от накрутки анонимных опросов)
    responses_per_ip_hour: int = 60
    # Перенос из NocoBase (python -m app.cli nocobase-fetch)
    nocobase_url: str = ''
    nocobase_api_key: str = ''

    db: SurveyDatabaseSettings = SurveyDatabaseSettings()
    smtp: SurveySmtpSettings = SurveySmtpSettings()
    auth: SurveyAuthSettings = SurveyAuthSettings()


settings = Settings()
sk_common.configure(settings)

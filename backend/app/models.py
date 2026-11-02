"""Реестр моделей для Alembic. Люди, вход и журнал — из sk_common."""

from sk_common import models as common_models
from sk_common.db import Base

from app.modules.responses import models as responses_models
from app.modules.surveys import models as surveys_models

__all__ = ['Base', 'common_models', 'responses_models', 'surveys_models']

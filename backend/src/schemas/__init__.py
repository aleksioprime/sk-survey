"""
Pydantic-схемы для валидации входящих данных.
"""

from pydantic import BaseModel, Field


class AnswerPayload(BaseModel):
    """Тело запроса при сохранении ответа на вопрос.

    Заполняется одно из полей в зависимости от типа вопроса:
    - text_value — для текстовых вопросов
    - rich_text_value — для форматированного текста
    - number_value — для числовых вопросов и генерируемых шкал
    - boolean_value — для вопросов да/нет
    - scale_item_id — для шкал с элементами
    - option_id — для одиночного выбора
    - option_ids — для множественного выбора (ManyToMany)
    """

    text_value: str | None = None
    rich_text_value: str | None = None
    number_value: float | None = None
    boolean_value: bool | None = None
    scale_item_id: int | None = None
    option_id: int | None = None
    option_ids: list[int] | None = Field(default=None, description='Для множественного выбора')
    is_skipped: bool = False

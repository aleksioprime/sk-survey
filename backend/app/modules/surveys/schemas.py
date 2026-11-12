from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.surveys.models import (
    MATRIX_TYPES,
    QUESTION_TYPES,
    SCALE_GENERATED,
    SCALE_ITEMS,
    TEXT_LIST,
    TEXT_LIST_MAX_ROWS,
)

_TYPE_PATTERN = '^(' + '|'.join(QUESTION_TYPES) + ')$'


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Шкалы ----------------------------------------------------------------------------------


class ScaleItemIn(BaseModel):
    id: int | None = None
    title: str = Field(max_length=255)
    description: str = ''
    value: str = Field(default='', max_length=100)
    score: float | None = None


class ScaleItemOut(ORMModel):
    id: int
    title: str
    description: str
    value: str
    score: float | None
    order: int


class ScaleIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ''
    scale_type: str = Field(default=SCALE_GENERATED, pattern=f'^({SCALE_GENERATED}|{SCALE_ITEMS})$')
    min_value: int = 1
    max_value: int = 10
    step: int = Field(default=1, ge=1)
    items: list[ScaleItemIn] = []

    @model_validator(mode='after')
    def _check(self):
        if self.scale_type == SCALE_GENERATED and self.min_value >= self.max_value:
            raise ValueError('Минимум шкалы должен быть меньше максимума')
        if self.scale_type == SCALE_ITEMS and not self.items:
            raise ValueError('Добавьте элементы шкалы')
        return self


class ScaleSurveyUsage(BaseModel):
    id: int
    title: str


class ScaleOut(ORMModel):
    id: int
    title: str
    description: str
    scale_type: str
    min_value: int
    max_value: int
    step: int
    items: list[ScaleItemOut]
    used_in: list[ScaleSurveyUsage] = []


# --- Вопросы --------------------------------------------------------------------------------


class MatrixRow(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class OptionIn(BaseModel):
    id: int | None = None
    title: str = Field(min_length=1, max_length=1000)
    description: str = ''
    value: str = Field(default='', max_length=255)
    score: float | None = None
    is_active: bool = True
    exclude_from_base: bool = False


class OptionOut(ORMModel):
    id: int
    title: str
    description: str
    value: str
    score: float | None
    order: int
    is_active: bool
    exclude_from_base: bool


class RangeIn(BaseModel):
    id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    from_value: float
    to_value: float


class RangeOut(ORMModel):
    id: int
    title: str
    from_value: float
    to_value: float
    order: int


class QuestionIn(BaseModel):
    section_id: int | None = None
    text: str = Field(min_length=1, max_length=5000)
    description: str = ''
    question_type: str = Field(pattern=_TYPE_PATTERN)
    is_required: bool = False
    is_active: bool = True
    scale_id: int | None = None
    min_selections: int | None = Field(default=None, ge=0)
    max_selections: int | None = Field(default=None, ge=1)
    min_rows: int | None = Field(default=None, ge=1, le=TEXT_LIST_MAX_ROWS)
    max_rows: int | None = Field(default=None, ge=1, le=TEXT_LIST_MAX_ROWS)
    min_number: float | None = None
    max_number: float | None = None
    is_options_shuffled: bool = False
    options: list[OptionIn] = []
    ranges: list[RangeIn] = []
    matrix_rows: list[MatrixRow] = Field(default=[], max_length=50)

    @model_validator(mode='after')
    def _check(self):
        if self.question_type in ('single_choice', 'multiple_choice', 'ranking') and len(self.options) < 2:
            raise ValueError('Добавьте хотя бы два варианта ответа')
        if self.question_type in MATRIX_TYPES:
            if not self.matrix_rows or len({row.id for row in self.matrix_rows}) != len(self.matrix_rows):
                raise ValueError('Добавьте строки матрицы с уникальными идентификаторами')
            if not 2 <= sum(o.is_active for o in self.options) <= 50:
                raise ValueError('В матрице должно быть от 2 до 50 активных столбцов')
        elif self.matrix_rows:
            raise ValueError('Строки поддерживаются только в матрице')
        if self.min_rows is not None or self.max_rows is not None:
            if self.question_type != TEXT_LIST:
                raise ValueError('Число строк задаётся только для списка текстовых ответов')
            if self.min_rows and self.max_rows and self.min_rows > self.max_rows:
                raise ValueError('Минимум строк больше максимума')
        if self.question_type == 'scale' and self.scale_id is None:
            raise ValueError('Выберите шкалу')
        if self.min_selections and self.max_selections and self.min_selections > self.max_selections:
            raise ValueError('Минимум выборов больше максимума')
        if self.min_number is not None and self.max_number is not None and self.min_number > self.max_number:
            raise ValueError('Минимальное число больше максимального')
        return self


class QuestionOut(ORMModel):
    id: int
    survey_id: int
    section_id: int | None
    text: str
    description: str
    question_type: str
    order: int
    is_required: bool
    is_active: bool
    scale_id: int | None
    min_selections: int | None
    max_selections: int | None
    min_rows: int | None
    max_rows: int | None
    min_number: float | None
    max_number: float | None
    is_options_shuffled: bool
    options: list[OptionOut]
    ranges: list[RangeOut]
    matrix_rows: list[MatrixRow]
    answers_count: int = 0


# --- Разделы и опросы -----------------------------------------------------------------------


class SectionIn(BaseModel):
    title: str = Field(default='', max_length=500)
    description: str = ''
    is_active: bool = True


class SectionOut(ORMModel):
    id: int
    title: str
    description: str
    order: int
    is_active: bool


class SurveyIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=100, pattern=r'^[a-z0-9_-]*$')
    description: str = ''
    intro_text: str = ''
    thank_you_text: str = ''
    is_active: bool = True
    is_anonymous: bool = True


class SurveyPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=100, pattern=r'^[a-z0-9_-]*$')
    description: str | None = None
    intro_text: str | None = None
    thank_you_text: str | None = None
    is_active: bool | None = None
    is_anonymous: bool | None = None


class MemberOut(BaseModel):
    user_id: int
    person_id: int | None
    email: str
    full_name: str
    role: str


class SurveyListItem(ORMModel):
    id: int
    title: str
    code: str | None
    is_active: bool
    is_anonymous: bool
    updated_at: datetime
    questions_count: int = 0
    publishings_count: int = 0
    result_publication_id: int | None = None
    responses_count: int = 0
    role: str | None = None


class SurveyOut(ORMModel):
    id: int
    title: str
    code: str | None
    description: str
    intro_text: str
    thank_you_text: str
    is_active: bool
    is_anonymous: bool
    created_at: datetime
    updated_at: datetime
    sections: list[SectionOut]
    questions: list[QuestionOut]
    members: list[MemberOut] = []
    role: str | None = None


class QuestionPlace(BaseModel):
    id: int
    section_id: int | None = None


class OrderIn(BaseModel):
    """Новый порядок: разделы по списку, вопросы по списку с разделом каждого."""

    sections: list[int] = []
    questions: list[QuestionPlace] = []


class MembersIn(BaseModel):
    editor_person_ids: list[int] = Field(default=[], description='Персоны-редакторы (сотрудники из справочника)')


class MemberAccessIn(BaseModel):
    role: Literal['owner', 'editor']
    user_id: int | None = None
    person_id: int | None = None

    @model_validator(mode='after')
    def check_identity(self):
        if (self.user_id is None) == (self.person_id is None):
            raise ValueError('Укажите user_id действующего участника или person_id сотрудника из справочника')
        return self


class SurveyAccessIn(BaseModel):
    members: list[MemberAccessIn]


class SurveyAccessOut(BaseModel):
    members: list[MemberOut]
    role: str | None


# --- Публикации -----------------------------------------------------------------------------


class PublishingIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    is_active: bool = True
    is_anonymous: bool = True
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    observer_person_ids: list[int] = []


class PublishingPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None
    is_anonymous: bool | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    observer_person_ids: list[int] | None = None


class ObserverOut(BaseModel):
    user_id: int
    person_id: int | None
    email: str
    full_name: str


class PublishingOut(ORMModel):
    id: int
    survey_id: int
    survey_title: str
    title: str
    public_token: str
    is_active: bool
    is_anonymous: bool
    opens_at: datetime | None
    closes_at: datetime | None
    created_at: datetime
    observers: list[ObserverOut] = []
    submitted_count: int = 0
    in_progress_count: int = 0
    status: Literal['open', 'scheduled', 'closed']
    can_edit: bool = False

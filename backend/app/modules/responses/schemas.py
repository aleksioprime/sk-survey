from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.modules.surveys.models import TEXT_LIST_MAX_ROWS, TEXT_LIST_ROW_LENGTH
from app.modules.surveys.schemas import MatrixRow, RangeOut, ScaleOut, SectionOut


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PublicOption(ORMModel):
    id: int
    title: str
    description: str


class PublicQuestion(ORMModel):
    id: int
    section_id: int | None
    text: str
    description: str
    question_type: str
    is_required: bool
    scale_id: int | None
    min_selections: int | None
    max_selections: int | None
    min_rows: int | None
    max_rows: int | None
    min_number: float | None
    max_number: float | None
    is_options_shuffled: bool
    options: list[PublicOption]
    ranges: list[RangeOut]
    matrix_rows: list[MatrixRow]


class PublicSurvey(BaseModel):
    publishing_title: str
    is_anonymous: bool
    requires_login: bool
    title: str
    description: str
    intro_text: str
    thank_you_text: str
    sections: list[SectionOut] = []
    questions: list[PublicQuestion] = []
    scales: list[ScaleOut] = []


class AnswerIn(BaseModel):
    text_value: str | None = Field(default=None, max_length=20000)
    text_rows: list[Annotated[str, Field(max_length=TEXT_LIST_ROW_LENGTH, pattern=r'^[^\x00-\x08\x0a-\x1f]*$')]] = (
        Field(default=[], max_length=TEXT_LIST_MAX_ROWS)
    )
    rich_text_value: str | None = Field(default=None, max_length=100000)
    number_value: float | None = None
    boolean_value: bool | None = None
    scale_item_id: int | None = None
    option_id: int | None = None
    option_ids: list[int] = Field(default=[], max_length=200)
    ranking: list[int] = Field(default=[], max_length=200, description='ID вариантов по порядку, первый — главный')
    matrix_choices: dict[str, Annotated[list[int], Field(min_length=1, max_length=50)]] = Field(
        default={}, max_length=50
    )
    is_skipped: bool = False


class AnswerOut(ORMModel):
    question_id: int
    text_value: str | None
    rich_text_value: str | None
    number_value: float | None
    boolean_value: bool | None
    scale_item_id: int | None
    option_id: int | None
    option_ids: list[int]
    ranking_ids: list[int]
    text_rows: list[str]
    matrix_choices: dict[str, list[int]]
    is_skipped: bool


class ResponseState(BaseModel):
    response_id: int
    status: str
    submitted_at: datetime | None
    answers: list[AnswerOut]


class StartResult(ResponseState):
    response_token: str | None = Field(default=None, description='Ключ прохождения: передавать в X-Response-Token')


class SubmitResult(BaseModel):
    status: str
    thank_you_text: str

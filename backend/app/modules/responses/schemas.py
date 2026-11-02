from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.surveys.schemas import RangeOut, ScaleOut, SectionOut


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
    min_number: float | None
    max_number: float | None
    is_options_shuffled: bool
    options: list[PublicOption]
    ranges: list[RangeOut]


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
    rich_text_value: str | None = Field(default=None, max_length=100000)
    number_value: float | None = None
    boolean_value: bool | None = None
    scale_item_id: int | None = None
    option_id: int | None = None
    option_ids: list[int] = Field(default=[], max_length=200)
    ranking: list[int] = Field(default=[], max_length=200, description='ID вариантов по порядку, первый — главный')
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

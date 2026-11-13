from datetime import datetime

from pydantic import BaseModel


class OptionStat(BaseModel):
    id: int | None
    title: str
    count: int
    percent: float


class DistributionItem(BaseModel):
    value: float
    count: int


class RangeStat(BaseModel):
    title: str
    from_value: float
    to_value: float
    count: int
    percent: float


class RankingStat(BaseModel):
    id: int
    title: str
    average_rank: float | None
    first_places: int


class TextAnswer(BaseModel):
    response_id: int
    text: str


class ChoiceBreakdown(BaseModel):
    base: int
    options: list[OptionStat] = []
    excluded: list[OptionStat] = []


class MatrixRowResult(ChoiceBreakdown):
    row_id: str
    title: str
    answered: int


class QuestionResult(BaseModel):
    question_id: int
    section_id: int | None
    text: str
    question_type: str
    is_active: bool
    is_required: bool
    answered: int
    skipped: int
    options: list[OptionStat] = []
    comparison: ChoiceBreakdown | None = None
    matrix_rows: list[MatrixRowResult] = []
    mean: float | None = None
    median: float | None = None
    min: float | None = None
    max: float | None = None
    distribution: list[DistributionItem] = []
    ranges: list[RangeStat] = []
    ranking: list[RankingStat] = []
    texts: list[TextAnswer] = []


class PublishingResults(BaseModel):
    publishing_id: int
    title: str
    survey_title: str
    is_anonymous: bool
    responses: int
    in_progress: int
    questions: list[QuestionResult]


class IndividualAnswer(BaseModel):
    question_id: int
    question: str
    text: str
    is_rich_text: bool = False


class IndividualResponse(BaseModel):
    id: str
    number: int
    submitted: bool
    started_at: datetime
    submitted_at: datetime | None
    respondent: str | None = None
    study_class: str | None = None
    answers: list[IndividualAnswer]


class IndividualResponses(BaseModel):
    page: int
    page_size: int
    responses: int
    in_progress: int
    items: list[IndividualResponse]

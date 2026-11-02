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


class QuestionResult(BaseModel):
    question_id: int
    section_id: int | None
    text: str
    question_type: str
    is_active: bool
    answered: int
    skipped: int
    options: list[OptionStat] = []
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

"""Прохождения опросов и ответы на вопросы."""

from datetime import datetime

from sk_common.db import Base, IdMixin, TimestampMixin
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

STATUS_IN_PROGRESS = 'in_progress'
STATUS_SUBMITTED = 'submitted'

answer_options = Table(
    'survey_answer_options',
    Base.metadata,
    Column('answer_id', BigInteger, ForeignKey('survey_answers.id', ondelete='CASCADE'), primary_key=True),
    Column('option_id', BigInteger, ForeignKey('survey_question_options.id', ondelete='CASCADE'), primary_key=True),
)


class Response(IdMixin, TimestampMixin, Base):
    """Одно прохождение публикации. Браузер держит токен прохождения, в БД — только его хеш."""

    __tablename__ = 'survey_responses'

    publishing_id: Mapped[int] = mapped_column(ForeignKey('survey_publishings.id', ondelete='CASCADE'), index=True)
    # Только у неанонимных публикаций
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_IN_PROGRESS, server_default=STATUS_IN_PROGRESS)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    answers: Mapped[list['Answer']] = relationship(
        back_populates='response', cascade='all, delete-orphan', lazy='selectin'
    )


class Answer(IdMixin, TimestampMixin, Base):
    """Ответ на вопрос. Заполнено одно поле по типу вопроса; выбор и порядок — в связанных таблицах."""

    __tablename__ = 'survey_answers'
    __table_args__ = (UniqueConstraint('response_id', 'question_id'),)

    response_id: Mapped[int] = mapped_column(ForeignKey('survey_responses.id', ondelete='CASCADE'), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('survey_questions.id', ondelete='CASCADE'), index=True)
    text_value: Mapped[str | None] = mapped_column(Text)
    rich_text_value: Mapped[str | None] = mapped_column(Text)
    number_value: Mapped[float | None] = mapped_column(Float)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    scale_item_id: Mapped[int | None] = mapped_column(ForeignKey('scale_items.id', ondelete='SET NULL'))
    option_id: Mapped[int | None] = mapped_column(ForeignKey('survey_question_options.id', ondelete='SET NULL'))
    is_skipped: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')

    response: Mapped[Response] = relationship(back_populates='answers')
    selected_options: Mapped[list['Option']] = relationship(secondary=answer_options, lazy='selectin')  # noqa: F821
    ranking: Mapped[list['RankingItem']] = relationship(
        back_populates='answer', cascade='all, delete-orphan', order_by='RankingItem.rank', lazy='selectin'
    )

    @property
    def option_ids(self) -> list[int]:
        return [option.id for option in self.selected_options]

    @property
    def ranking_ids(self) -> list[int]:
        return [item.option_id for item in self.ranking]


class RankingItem(IdMixin, TimestampMixin, Base):
    __tablename__ = 'survey_answer_ranking_items'

    answer_id: Mapped[int] = mapped_column(ForeignKey('survey_answers.id', ondelete='CASCADE'), index=True)
    option_id: Mapped[int] = mapped_column(ForeignKey('survey_question_options.id', ondelete='CASCADE'))
    rank: Mapped[int] = mapped_column(Integer)

    answer: Mapped[Answer] = relationship(back_populates='ranking')

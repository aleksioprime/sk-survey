"""Конструктор опросов: опросы, разделы, вопросы, варианты, шкалы, публикации.

Структура повторяет коллекции NocoBase, из которых переносятся данные (ID сохраняются).
"""

from datetime import datetime

from sk_common.db import Base, IdMixin, TimestampMixin
from sk_common.people.models import User
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

QUESTION_TYPES = (
    'text',  # Текст
    'rich_text',  # Форматированный текст
    'single_choice',  # Одиночный выбор
    'multiple_choice',  # Множественный выбор
    'number',  # Число
    'yes_no',  # Да/Нет
    'scale',  # Шкала
    'ranking',  # Расставить по порядку
)
CHOICE_TYPES = ('single_choice', 'multiple_choice', 'ranking')

SCALE_GENERATED = 'generated'  # значения от min до max с шагом
SCALE_ITEMS = 'items'  # значения — элементы шкалы

ROLE_OWNER = 'owner'
ROLE_EDITOR = 'editor'

publishing_observers = Table(
    'publishing_observers',
    Base.metadata,
    Column('publishing_id', BigInteger, ForeignKey('survey_publishings.id', ondelete='CASCADE'), primary_key=True),
    Column('user_id', BigInteger, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
)


class Scale(IdMixin, TimestampMixin, Base):
    """Шкала оценки, общая для опросов (например, «1–10»)."""

    __tablename__ = 'scales'

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    scale_type: Mapped[str] = mapped_column(String(20), default=SCALE_GENERATED, server_default=SCALE_GENERATED)
    min_value: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    max_value: Mapped[int] = mapped_column(Integer, default=10, server_default='10')
    step: Mapped[int] = mapped_column(Integer, default=1, server_default='1')

    items: Mapped[list['ScaleItem']] = relationship(
        back_populates='scale', cascade='all, delete-orphan', order_by='ScaleItem.order', lazy='selectin'
    )


class ScaleItem(IdMixin, TimestampMixin, Base):
    __tablename__ = 'scale_items'

    scale_id: Mapped[int] = mapped_column(ForeignKey('scales.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    value: Mapped[str] = mapped_column(String(100), default='', server_default='')
    score: Mapped[float | None] = mapped_column(Float)
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    scale: Mapped[Scale] = relationship(back_populates='items')


class Survey(IdMixin, TimestampMixin, Base):
    __tablename__ = 'surveys'

    title: Mapped[str] = mapped_column(String(500))
    code: Mapped[str | None] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    intro_text: Mapped[str] = mapped_column(Text, default='', server_default='')
    thank_you_text: Mapped[str] = mapped_column(Text, default='', server_default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    # Значение по умолчанию для новых публикаций
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))

    sections: Mapped[list['Section']] = relationship(
        back_populates='survey', cascade='all, delete-orphan', order_by='Section.order', lazy='selectin'
    )
    questions: Mapped[list['Question']] = relationship(
        back_populates='survey', cascade='all, delete-orphan', order_by='Question.order', lazy='selectin'
    )
    members: Mapped[list['SurveyMember']] = relationship(
        back_populates='survey', cascade='all, delete-orphan', lazy='selectin'
    )


class SurveyMember(Base):
    """Кто ведёт опрос: владелец (создатель) и редакторы."""

    __tablename__ = 'survey_members'

    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_EDITOR, server_default=ROLE_EDITOR)

    survey: Mapped[Survey] = relationship(back_populates='members')
    user: Mapped[User] = relationship(lazy='joined')


class Section(IdMixin, TimestampMixin, Base):
    __tablename__ = 'survey_sections'

    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(500), default='', server_default='')
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')

    survey: Mapped[Survey] = relationship(back_populates='sections')


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = 'survey_questions'

    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey('survey_sections.id', ondelete='SET NULL'))
    text: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    question_type: Mapped[str] = mapped_column(String(30))
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    scale_id: Mapped[int | None] = mapped_column(ForeignKey('scales.id', ondelete='SET NULL'))
    min_selections: Mapped[int | None] = mapped_column(Integer)
    max_selections: Mapped[int | None] = mapped_column(Integer)
    min_number: Mapped[float | None] = mapped_column(Float)
    max_number: Mapped[float | None] = mapped_column(Float)
    is_options_shuffled: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')

    survey: Mapped[Survey] = relationship(back_populates='questions')
    scale: Mapped[Scale | None] = relationship(lazy='selectin')
    options: Mapped[list['Option']] = relationship(
        back_populates='question', cascade='all, delete-orphan', order_by='Option.order', lazy='selectin'
    )
    ranges: Mapped[list['ScaleRange']] = relationship(
        back_populates='question', cascade='all, delete-orphan', order_by='ScaleRange.order', lazy='selectin'
    )


class Option(IdMixin, TimestampMixin, Base):
    """Вариант ответа для выбора и расстановки по порядку."""

    __tablename__ = 'survey_question_options'

    question_id: Mapped[int] = mapped_column(ForeignKey('survey_questions.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str] = mapped_column(Text, default='', server_default='')
    value: Mapped[str] = mapped_column(String(255), default='', server_default='')
    score: Mapped[float | None] = mapped_column(Float)
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')

    question: Mapped[Question] = relationship(back_populates='options')


class ScaleRange(IdMixin, TimestampMixin, Base):
    """Диапазон значений шкалы для отчёта: «1–3 — крайне низкая»."""

    __tablename__ = 'survey_question_scale_ranges'

    question_id: Mapped[int] = mapped_column(ForeignKey('survey_questions.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    from_value: Mapped[float] = mapped_column(Float)
    to_value: Mapped[float] = mapped_column(Float)
    order: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

    question: Mapped[Question] = relationship(back_populates='ranges')


class Publishing(IdMixin, TimestampMixin, Base):
    """Выпуск опроса по ссылке /s/<public_token>. Ответы собираются по публикации."""

    __tablename__ = 'survey_publishings'

    survey_id: Mapped[int] = mapped_column(ForeignKey('surveys.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(500))
    public_token: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    # Анонимная — без входа, ответ не связан с человеком. Иначе вход через SkolStream и один ответ на человека
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))

    survey: Mapped[Survey] = relationship(lazy='joined')
    observers: Mapped[list[User]] = relationship(secondary=publishing_observers, lazy='selectin')

"""Выбор публикаций и условий для отчёта по одному опросу."""

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from pydantic import Field
from sk_common.deps import CurrentUser, Db
from sqlalchemy import select

from app.modules.responses.models import STATUS_SUBMITTED, Answer, Response, answer_options
from app.modules.surveys.models import Publishing
from app.modules.surveys.permissions import viewable_publishing
from app.modules.surveys.service import observed_publication_ids

CHOICE = ('single_choice', 'multiple_choice')
ReportId = Annotated[int, Field(gt=0, le=2**63 - 1)]


def available_publishings(publishing, can_edit, user):
    query = select(Publishing).where(Publishing.survey_id == publishing.survey_id)
    if not can_edit:
        query = query.where(Publishing.id.in_(observed_publication_ids(user)))
    return query


@dataclass
class ReportSelection:
    publishing: Publishing
    publications: dict[int, Publishing]
    options: dict[int, set[int]] = field(default_factory=dict)

    @property
    def combined(self):
        return len(self.publications) > 1

    @property
    def title(self):
        return f'{self.publishing.survey.title} - общая статистика' if self.combined else self.publishing.title

    @property
    def anonymous(self):
        return all(p.is_anonymous for p in self.publications.values())

    def response_query(self, include_in_progress):
        query = select(Response).where(Response.publishing_id.in_(self.publications))
        if not include_in_progress:
            query = query.where(Response.status == STATUS_SUBMITTED)
        for question_id, option_ids in self.options.items():
            multiple = select(answer_options.c.answer_id).where(answer_options.c.option_id.in_(option_ids))
            query = query.where(
                Response.answers.any(
                    (Answer.question_id == question_id)
                    & Answer.is_skipped.is_(False)
                    & (Answer.option_id.in_(option_ids) | Answer.id.in_(multiple))
                )
            )
        return query


async def report_selection(
    publishing_id: int,
    db: Db,
    user: CurrentUser,
    publication: Annotated[list[ReportId] | None, Query()] = None,
    option: Annotated[list[ReportId] | None, Query()] = None,
) -> ReportSelection:
    publishing, can_edit = await viewable_publishing(db, publishing_id, user)
    publications = {publishing.id: publishing}
    extra = set(publication or ()) - publications.keys()
    if extra:
        query = available_publishings(publishing, can_edit, user).where(Publishing.id.in_(extra))
        publications.update((p.id, p) for p in await db.scalars(query))
        if extra - publications.keys():
            raise HTTPException(404, 'Публикация не найдена')
    selected = set(option or ())
    filters = {}
    if selected:
        for question in publishing.survey.questions:
            if question.question_type in CHOICE:
                matches = selected.intersection(o.id for o in question.options)
                if matches:
                    filters[question.id] = matches
                    selected -= matches
        if selected:
            raise HTTPException(422, 'Вариант фильтра не относится к вопросу с выбором ответа в этом опросе')
    return ReportSelection(publishing, publications, filters)


Selection = Annotated[ReportSelection, Depends(report_selection)]

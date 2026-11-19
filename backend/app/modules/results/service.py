"""Результаты публикации: сводка по вопросам и выгрузка ответов. Считается в памяти - ответов сотни."""

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font
from sk_common.people.models import User
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.responses.models import STATUS_SUBMITTED, Answer, Response
from app.modules.results.excel_layout import format_sheet
from app.modules.results.office_text import rich_text_to_text, xml_text
from app.modules.results.schemas import (
    ChoiceBreakdown,
    DistributionItem,
    IndividualAnswer,
    IndividualResponse,
    IndividualResponses,
    MatrixRowResult,
    OptionStat,
    PublishingResults,
    QuestionResult,
    RangeStat,
    RankingStat,
    TextAnswer,
)
from app.modules.results.selection import CHOICE, ReportSelection
from app.modules.surveys.models import MATRIX_TYPES, SCALE_GENERATED, TEXT_LIST, Publishing, Question, Scale

NUMERIC = ('number', 'scale')
TEXTS = ('text', 'short_text', 'rich_text', TEXT_LIST, 'date')
RESPONSES_PER_PAGE = 20
MOSCOW = ZoneInfo('Europe/Moscow')


@dataclass
class Dataset:
    selection: ReportSelection
    questions: list[Question]
    responses: list[Response]
    scales: dict[int, Scale]
    users: dict[int, User]

    def respondent(self, response: Response) -> User | None:
        if self.selection.publications[response.publishing_id].is_anonymous:
            return None
        return self.users.get(response.user_id)


def _ordered_responses(query):
    return query.order_by(Response.submitted_at.nulls_last(), Response.created_at, Response.id)


async def load(db: AsyncSession, selection: ReportSelection, include_in_progress: bool = False) -> Dataset:
    responses = list(await db.scalars(_ordered_responses(selection.response_query(include_in_progress))))
    return await _load_dataset(db, selection, responses)


async def load_response(db: AsyncSession, publishing: Publishing, response_id: int) -> Dataset | None:
    response = await db.scalar(
        select(Response).where(Response.publishing_id == publishing.id, Response.id == response_id)
    )
    return (
        await _load_dataset(db, ReportSelection(publishing, {publishing.id: publishing}), [response])
        if response
        else None
    )


async def _load_dataset(db: AsyncSession, selection: ReportSelection, responses: list[Response]) -> Dataset:
    answered = {a.question_id for r in responses for a in r.answers}
    questions = [
        q
        for q in await db.scalars(
            select(Question).where(Question.survey_id == selection.publishing.survey_id).order_by(Question.order)
        )
        if q.is_active or q.id in answered
    ]
    scale_ids = {q.scale_id for q in questions if q.scale_id}
    scales = {s.id: s for s in await db.scalars(select(Scale).where(Scale.id.in_(scale_ids or {0})))}
    user_ids = {r.user_id for r in responses if r.user_id and not selection.publications[r.publishing_id].is_anonymous}
    users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    return Dataset(selection, questions, responses, scales, users)


def _answers(data: Dataset, question: Question) -> list[Answer]:
    return [a for r in data.responses for a in r.answers if a.question_id == question.id]


def _percent(count: int, total: int) -> float:
    return round(count * 100 / total, 1) if total else 0.0


def summarize(data: Dataset) -> PublishingResults:
    total = len(data.responses)
    results = []
    for question in data.questions:
        answers = _answers(data, question)
        skipped = sum(1 for a in answers if a.is_skipped)
        result = QuestionResult(
            question_id=question.id,
            section_id=question.section_id,
            text=question.text,
            question_type=question.question_type,
            is_active=question.is_active,
            is_required=question.is_required,
            answered=0,
            skipped=skipped,
        )
        kind = question.question_type
        given = [a for a in answers if not a.is_skipped]
        if kind in CHOICE:
            selections = (
                [[a.option_id] for a in given if a.option_id]
                if kind == 'single_choice'
                else [a.option_ids for a in given if a.option_ids]
            )
            result.answered = len(selections)
            selected_options = data.selection.options.get(question.id)
            breakdown = _choice_breakdown(question, selections, selected_options)
            if breakdown.excluded:
                result.comparison = breakdown
            if selected_options:
                option_count = len(breakdown.options) + len(breakdown.excluded)
                breakdown.options = [o for o in breakdown.options if o.id in selected_options]
                breakdown.excluded = [o for o in breakdown.excluded if o.id in selected_options]
                result.hidden_options_count = option_count - len(breakdown.options) - len(breakdown.excluded)
            result.options = breakdown.options
        elif kind in MATRIX_TYPES:
            result.answered = sum(bool(a.matrix_choices) for a in given)
            for row in question.matrix_rows:
                row_id = row['id']
                selections = [a.matrix_choices[row_id] for a in given if row_id in a.matrix_choices]
                result.matrix_rows.append(
                    MatrixRowResult(
                        row_id=row_id,
                        title=row['title'],
                        answered=len(selections),
                        **_choice_breakdown(question, selections).model_dump(),
                    )
                )
        elif kind == 'yes_no':
            values = [a.boolean_value for a in given if a.boolean_value is not None]
            result.answered = len(values)
            result.options = [
                OptionStat(id=None, title=title, count=n, percent=_percent(n, len(values)))
                for title, n in (('Да', values.count(True)), ('Нет', values.count(False)))
            ]
        elif kind in NUMERIC:
            values = [a.number_value for a in given if a.number_value is not None]
            result.answered = len(values)
            _numeric(result, question, values, data.scales.get(question.scale_id))
        elif kind == 'ranking':
            ranked = [a for a in given if a.ranking]
            result.answered = len(ranked)
            result.ranking = _ranking(question, ranked)
        elif kind in TEXTS:
            values = [
                (
                    a.response_id,
                    answer_text(question, a, None)
                    if kind in (TEXT_LIST, 'date')
                    else a.text_value or a.rich_text_value,
                )
                for a in given
            ]
            texts = [TextAnswer(response_id=response_id, text=value) for response_id, value in values if value]
            result.answered = len(texts)
            result.texts = texts
        results.append(result)
    in_progress = sum(1 for r in data.responses if r.status != STATUS_SUBMITTED)
    return PublishingResults(
        publishing_id=data.selection.publishing.id,
        title=data.selection.title,
        survey_title=data.selection.publishing.survey.title,
        is_anonymous=data.selection.anonymous,
        responses=total - in_progress,
        in_progress=in_progress,
        questions=results,
    )


def _choice_breakdown(
    question: Question, selections: list[list[int]], selected_options: set[int] | None = None
) -> ChoiceBreakdown:
    excluded = {o.id for o in question.options if o.exclude_from_base}
    counts = Counter(option_id for selected in selections for option_id in selected)
    result = ChoiceBreakdown(base=sum(bool(set(selected) - excluded) for selected in selections))
    for option in question.options:
        count = counts[option.id]
        if not option.is_active and not count and option.id not in (selected_options or ()):
            continue
        separate = option.id in excluded
        denominator = len(selections) if separate else result.base
        stat = OptionStat(
            id=option.id,
            title=option.title,
            count=count,
            percent=_percent(count, denominator),
        )
        (result.excluded if separate else result.options).append(stat)
    return result


def _numeric(result: QuestionResult, question: Question, values: list[float], scale: Scale | None) -> None:
    if not values:
        return
    result.mean = round(statistics.fmean(values), 2)
    result.median = statistics.median(values)
    result.min = min(values)
    result.max = max(values)
    counts = Counter(values)
    if scale and scale.scale_type == SCALE_GENERATED:
        steps = range(scale.min_value, scale.max_value + 1, scale.step)
        result.distribution = [DistributionItem(value=float(v), count=counts.get(float(v), 0)) for v in steps]
    else:
        result.distribution = [DistributionItem(value=v, count=n) for v, n in sorted(counts.items())]
    result.ranges = [
        RangeStat(
            title=r.title,
            from_value=r.from_value,
            to_value=r.to_value,
            count=(n := sum(1 for v in values if r.from_value <= v <= r.to_value)),
            percent=_percent(n, len(values)),
        )
        for r in question.ranges
    ]


def _ranking(question: Question, answers: list[Answer]) -> list[RankingStat]:
    stats = []
    for option in question.options:
        ranks = [item.rank for a in answers for item in a.ranking if item.option_id == option.id]
        if not option.is_active and not ranks:
            continue
        stats.append(
            RankingStat(
                id=option.id,
                title=option.title,
                average_rank=round(statistics.fmean(ranks), 2) if ranks else None,
                first_places=ranks.count(1),
            )
        )
    return sorted(stats, key=lambda s: (s.average_rank is None, s.average_rank or 0))


# --- Выгрузка -------------------------------------------------------------------------------


def answer_text(question: Question, answer: Answer | None, scale: Scale | None, *, separator: str = '; ') -> str:
    if answer is None:
        return ''
    if answer.is_skipped:
        return 'Пропущен'
    kind = question.question_type
    if kind in ('text', 'short_text'):
        return answer.text_value or ''
    if kind == 'date':
        return answer.date_value.isoformat() if answer.date_value else ''
    if kind == TEXT_LIST:
        return '\n'.join(answer.text_rows)
    if kind == 'rich_text':
        return answer.rich_text_value or ''
    titles = {o.id: o.title for o in question.options}
    if kind == 'single_choice':
        return titles.get(answer.option_id, '')
    if kind == 'multiple_choice':
        return separator.join(titles.get(i, '') for i in answer.option_ids)
    if kind == 'ranking':
        return separator.join(f'{item.rank}. {titles.get(item.option_id, "")}' for item in answer.ranking)
    if kind == 'yes_no':
        return '' if answer.boolean_value is None else ('Да' if answer.boolean_value else 'Нет')
    if kind == 'scale' and answer.scale_item_id and scale:
        return next((i.title for i in scale.items if i.id == answer.scale_item_id), '')
    if answer.number_value is not None:
        return f'{answer.number_value:g}'
    return ''


def matrix_values(question: Question, answer: Answer | None) -> list[str]:
    choices = answer.matrix_choices if answer else {}
    titles = {option.id: option.title for option in question.options}
    return [
        'Пропущен'
        if answer and answer.is_skipped
        else '; '.join(titles[oid] for oid in choices.get(row['id'], []) if oid in titles)
        for row in question.matrix_rows
    ]


def _individual_answer(question: Question, answer: Answer, scale: Scale | None) -> IndividualAnswer:
    if question.question_type in MATRIX_TYPES and not answer.is_skipped:
        text = '\n'.join(
            f"{row['title']}: {value}"
            for row, value in zip(question.matrix_rows, matrix_values(question, answer), strict=True)
            if value
        )
    else:
        text = answer_text(question, answer, scale)
    return IndividualAnswer(
        question_id=question.id,
        question=question.text,
        text=text,
        is_rich_text=question.question_type == 'rich_text' and not answer.is_skipped,
    )


async def individual_responses(
    db: AsyncSession, selection: ReportSelection, include_in_progress: bool, page: int
) -> IndividualResponses:
    query = selection.response_query(include_in_progress)
    total, submitted = (
        await db.execute(
            query.with_only_columns(func.count(), func.count().filter(Response.status == STATUS_SUBMITTED))
        )
    ).one()
    page = min(page, max(1, (total + RESPONSES_PER_PAGE - 1) // RESPONSES_PER_PAGE))
    offset = (page - 1) * RESPONSES_PER_PAGE
    responses = list(await db.scalars(_ordered_responses(query).offset(offset).limit(RESPONSES_PER_PAGE)))
    data = await _load_dataset(db, selection, responses)
    items = []
    for number, response in enumerate(data.responses, offset + 1):
        by_question = {answer.question_id: answer for answer in response.answers}
        user = data.respondent(response)
        person = user.person if user else None
        answers = [
            _individual_answer(question, by_question[question.id], data.scales.get(question.scale_id))
            for question in data.questions
            if question.id in by_question
        ]
        items.append(
            IndividualResponse(
                id=str(response.id),
                publishing_id=str(response.publishing_id),
                number=number,
                submitted=response.status == STATUS_SUBMITTED,
                started_at=response.created_at,
                submitted_at=response.submitted_at,
                respondent=(person.full_name if person else '') or (user.email if user else None),
                study_class=person.study_class.name if person and person.study_class else None,
                answers=[answer for answer in answers if answer.text],
            )
        )
    return IndividualResponses(
        page=page, page_size=RESPONSES_PER_PAGE, responses=submitted, in_progress=total - submitted, items=items
    )


async def delete_response(db: AsyncSession, publishing: Publishing, response_id: int) -> bool:
    deleted_id = await db.scalar(
        delete(Response)
        .where(Response.id == response_id, Response.publishing_id == publishing.id)
        .returning(Response.id)
    )
    return deleted_id is not None


def _excel_time(value: datetime | None) -> datetime | None:
    return value.astimezone(MOSCOW).replace(tzinfo=None) if value else None


def export_xlsx(data: Dataset) -> bytes:
    book = Workbook(iso_dates=True)
    sheet = book.active
    sheet.title = 'Ответы'
    personal = not data.selection.anonymous
    header = ['№', 'Публикация'] if data.selection.combined else ['№']
    if personal:
        header += ['Отправлен (МСК)', 'ФИО', 'Email', 'Класс']
    for question in data.questions:
        if question.question_type in MATRIX_TYPES:
            header.extend(f"{question.text} / {row['title']}" for row in question.matrix_rows)
        else:
            header.append(question.text)
    header.append('Начало попытки (МСК)')
    if not personal:
        header.append('Отправлен (МСК)')
    sheet.append([xml_text(label) for label in header])
    for number, response in enumerate(data.responses, 1):
        by_question = {a.question_id: a for a in response.answers}
        row = [number]
        if data.selection.combined:
            row.append(data.selection.publications[response.publishing_id].title)
        if personal:
            user = data.respondent(response)
            person = user.person if user else None
            row += [
                _excel_time(response.submitted_at),
                person.full_name if person else '',
                user.email if user else '',
                person.study_class.name if person and person.study_class else '',
            ]
        for question in data.questions:
            answer = by_question.get(question.id)
            if question.question_type in MATRIX_TYPES:
                row.extend(matrix_values(question, answer))
            elif question.question_type == 'date' and answer and not answer.is_skipped and answer.date_value:
                row.append(answer.date_value)
            else:
                value = answer_text(question, answer, data.scales.get(question.scale_id))
                row.append(rich_text_to_text(value) if question.question_type == 'rich_text' else value)
        row.append(_excel_time(response.created_at))
        if not personal:
            row.append(_excel_time(response.submitted_at))
        sheet.append([xml_text(value) if isinstance(value, str) else value for value in row])
    sheet.freeze_panes = 'C2' if personal else 'B2'

    summary = book.create_sheet('Сводка')
    summary.append(
        ['Вопрос / строка матрицы', 'Ответ', 'Количество', '%', 'База', 'От чего рассчитан %', 'Обязательность']
    )
    for result in summarize(data).questions:
        summary.append([xml_text(result.text)])
        summary.cell(summary.max_row, 1).font = Font(bold=True)
        summary.cell(summary.max_row, 7, 'Обязательный' if result.is_required else 'Необязательный')
        if result.hidden_options_count:
            summary.append(['', 'Остальные варианты скрыты фильтром.'])
        if result.comparison:
            _export_choices(summary, result.comparison, result.answered, has_comparison=True)
        else:
            for option in result.options:
                summary.append(['', xml_text(option.title), option.count, option.percent])
        for row in result.matrix_rows:
            summary.append([xml_text(row.title)])
            _export_choices(summary, row, row.answered)
        for item in result.ranking:
            summary.append(['', f'{xml_text(item.title)} - средняя позиция', item.average_rank, None])
        for item in result.ranges:
            summary.append(['', xml_text(item.title), item.count, item.percent])
        if result.mean is not None:
            summary.append(['', 'Среднее', result.mean, None])
    summary.freeze_panes = 'A2'
    for worksheet in book:
        format_sheet(worksheet)
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _export_choices(sheet, breakdown: ChoiceBreakdown, answered: int, *, has_comparison: bool = False) -> None:
    summary_base = 'Сравнимые ответы' if has_comparison or breakdown.excluded else 'Ответившие'
    for option in breakdown.options:
        percent = option.percent if breakdown.base else None
        sheet.append(['', xml_text(option.title), option.count, percent, breakdown.base, summary_base])
    for option in breakdown.excluded:
        sheet.append(
            ['', xml_text(option.title), option.count, option.percent if answered else None, answered, 'Все ответившие']
        )

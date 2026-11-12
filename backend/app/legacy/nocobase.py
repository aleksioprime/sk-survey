"""
Перенос опросов из NocoBase.

    python -m app.cli nocobase-fetch /data/nocobase   # API NocoBase → JSON-файлы (только чтение)
    python -m app.cli nocobase-load /data/nocobase    # JSON-файлы → база SK Survey

ID записей и публичные токены публикаций сохраняются: старые ссылки /s/<токен> продолжают работать.
Ключи незаконченных прохождений переносятся хешем - человек может дописать начатый опрос.
Повторная загрузка пропускает уже перенесённые записи.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import nh3
from sk_common.people.models import PERSON_SOURCE_LOCAL, Person
from sk_common.people.service import ensure_user, normalize_email
from sk_common.security import hash_secret
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.responses.models import STATUS_IN_PROGRESS, STATUS_SUBMITTED, Answer, RankingItem, Response
from app.modules.responses.service import RICH_TEXT_TAGS
from app.modules.surveys.models import (
    QUESTION_TYPES,
    SCALE_GENERATED,
    Option,
    Publishing,
    Question,
    Scale,
    ScaleItem,
    ScaleRange,
    Section,
    Survey,
    SurveyMember,
)

logger = logging.getLogger('sk_survey.nocobase')

# Коллекция → связи, которые нужно получить вместе с записями
COLLECTIONS: dict[str, list[str]] = {
    'persons': [],
    'surveys': [],
    'survey_sections': [],
    'survey_scales': [],
    'survey_scale_items': [],
    'survey_questions': [],
    'survey_question_options': [],
    'survey_question_scale_ranges': [],
    'survey_publishings': ['observers'],
    'survey_responses': [],
    'survey_answers': ['options'],
    'survey_answer_ranking_items': [],
}


async def fetch(base_url: str, api_key: str, target: Path, page_size: int = 500) -> dict[str, int]:
    """Все записи нужных коллекций постранично. Ничего не меняет в NocoBase."""
    target.mkdir(parents=True, exist_ok=True)
    counts = {}
    headers = {'Authorization': f'Bearer {api_key}', 'X-Role': 'root'}
    async with httpx.AsyncClient(base_url=base_url.rstrip('/'), headers=headers, timeout=60) as client:
        for name, appends in COLLECTIONS.items():
            rows: list[dict] = []
            page = 1
            while True:
                params: list[tuple[str, Any]] = [('page', page), ('pageSize', page_size), ('sort', 'id')]
                params += [('appends[]', a) for a in appends]
                response = await client.get(f'/api/{name}:list', params=params)
                response.raise_for_status()
                body = response.json()
                chunk = body.get('data') or []
                rows += chunk
                meta = body.get('meta') or {}
                if len(chunk) < page_size or page >= meta.get('totalPage', page):
                    break
                page += 1
            (target / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
            counts[name] = len(rows)
            logger.info('%s: %s записей', name, len(rows))
    return counts


# --- Загрузка --------------------------------------------------------------------------------


def _read(source: Path, name: str) -> list[dict]:
    path = source / f'{name}.json'
    return json.loads(path.read_text()) if path.exists() else []


def _dt(value) -> datetime | None:
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')) if value else None


def _text(value, limit: int | None = None) -> str:
    text = (str(value) if value is not None else '').strip()
    return text[:limit] if limit else text


def _int(value) -> int | None:
    return int(value) if value not in (None, '') else None


def _ids(value) -> list[int]:
    """Связь «многие ко многим» в ответе API: список объектов или id."""
    return [int(v['id'] if isinstance(v, dict) else v) for v in value or []]


def _stamps(row: dict) -> dict:
    created = _dt(row.get('createdAt'))
    return {'created_at': created, 'updated_at': _dt(row.get('updatedAt')) or created} if created else {}


class Loader:
    def __init__(self, session: AsyncSession, source: Path):
        self.session = session
        self.data = {name: _read(source, name) for name in COLLECTIONS}
        self.persons = {int(p['id']): p for p in self.data['persons']}
        self.counts: dict[str, int] = {}
        self.skipped: dict[str, list] = {}

    def skip(self, kind: str, nb_id, reason: str) -> None:
        self.skipped.setdefault(kind, []).append({'id': nb_id, 'reason': reason})

    def count(self, kind: str) -> None:
        self.counts[kind] = self.counts.get(kind, 0) + 1

    async def _exists(self, model, nb_id: int) -> bool:
        return await self.session.get(model, nb_id) is not None

    async def person_user(self, nb_person_id: int):
        """Учётная запись SK Survey для персоны NocoBase (наблюдатель публикации)."""
        row = self.persons.get(nb_person_id)
        if row is None:
            self.skip('observers', nb_person_id, 'персона не найдена в выгрузке')
            return None
        email = normalize_email(row.get('email') or '')
        person = None
        if row.get('skolstream_id'):
            person = await self.session.scalar(select(Person).where(Person.skolstream_id == row['skolstream_id']))
        if person is None and email:
            person = await self.session.scalar(select(Person).where(Person.email == email))
        if person is None:
            if not email:
                self.skip('observers', nb_person_id, 'у персоны нет email')
                return None
            # Войдёт через SkolStream - персона объединится с записью из справочника по email
            person = Person(
                source=PERSON_SOURCE_LOCAL,
                email=email,
                last_name=_text(row.get('last_name'), 100),
                first_name=_text(row.get('first_name'), 100),
                middle_name=_text(row.get('middle_name'), 100),
                is_employee=True,
            )
            self.session.add(person)
            await self.session.flush()
        return await ensure_user(self.session, person, person.email or email)

    async def run(self, owner_email: str | None) -> dict:
        owner = None
        if owner_email:
            from sk_common.people.service import find_or_create_user_by_email

            owner = await find_or_create_user_by_email(self.session, owner_email)

        for row in self.data['survey_scales']:
            if await self._exists(Scale, int(row['id'])):
                continue
            self.session.add(
                Scale(
                    id=int(row['id']),
                    title=_text(row.get('title'), 255) or 'Шкала',
                    description=_text(row.get('description')),
                    scale_type=row.get('scale_type') or SCALE_GENERATED,
                    min_value=_int(row.get('min_value')) or 1,
                    max_value=_int(row.get('max_value')) or 10,
                    step=_int(row.get('step')) or 1,
                    **_stamps(row),
                )
            )
            self.count('scales')
        await self.session.flush()
        for row in self.data['survey_scale_items']:
            if await self._exists(ScaleItem, int(row['id'])):
                continue
            self.session.add(
                ScaleItem(
                    id=int(row['id']),
                    scale_id=int(row['scale_id']),
                    title=_text(row.get('title'), 255),
                    description=_text(row.get('description')),
                    value=_text(row.get('value'), 100),
                    score=row.get('score'),
                    order=_int(row.get('order')) or 0,
                    **_stamps(row),
                )
            )
            self.count('scale_items')

        for row in self.data['surveys']:
            if await self._exists(Survey, int(row['id'])):
                continue
            survey = Survey(
                id=int(row['id']),
                title=_text(row.get('title'), 500),
                code=_text(row.get('code'), 100) or None,
                description=_text(row.get('description')),
                intro_text=_text(row.get('intro_text')),
                thank_you_text=_text(row.get('thank_you_text')),
                is_active=bool(row.get('is_active', True)),
                is_anonymous=row.get('is_anonymous') is not False,
                created_by_id=owner.id if owner else None,
                **_stamps(row),
            )
            if owner:
                survey.members = [SurveyMember(user_id=owner.id)]
            self.session.add(survey)
            self.count('surveys')
        await self.session.flush()

        for row in self.data['survey_sections']:
            if await self._exists(Section, int(row['id'])):
                continue
            self.session.add(
                Section(
                    id=int(row['id']),
                    survey_id=int(row['survey_id']),
                    title=_text(row.get('title'), 500),
                    description=_text(row.get('description')),
                    order=_int(row.get('order')) or 0,
                    is_active=row.get('is_active') is not False,
                    **_stamps(row),
                )
            )
            self.count('sections')
        await self.session.flush()

        for row in self.data['survey_questions']:
            if await self._exists(Question, int(row['id'])):
                continue
            if row.get('question_type') not in QUESTION_TYPES:
                self.skip('questions', row['id'], f'неизвестный тип {row.get("question_type")}')
                continue
            self.session.add(
                Question(
                    id=int(row['id']),
                    survey_id=int(row['survey_id']),
                    section_id=_int(row.get('section_id')),
                    text=_text(row.get('text')) or '-',
                    description=_text(row.get('description')),
                    question_type=row['question_type'],
                    order=_int(row.get('order')) or 0,
                    is_required=bool(row.get('is_required')),
                    is_active=row.get('is_active') is not False,
                    scale_id=_int(row.get('scale_id')),
                    min_selections=_int(row.get('min_selections')),
                    max_selections=_int(row.get('max_selections')),
                    min_number=row.get('min_number'),
                    max_number=row.get('max_number'),
                    is_options_shuffled=bool(row.get('is_options_shuffled')),
                    **_stamps(row),
                )
            )
            self.count('questions')
        await self.session.flush()

        for row in self.data['survey_question_options']:
            if await self._exists(Option, int(row['id'])):
                continue
            self.session.add(
                Option(
                    id=int(row['id']),
                    question_id=int(row['question_id']),
                    title=_text(row.get('title'), 1000) or '-',
                    description=_text(row.get('description')),
                    value=_text(row.get('value'), 255),
                    score=row.get('score'),
                    order=_int(row.get('order')) or 0,
                    is_active=row.get('is_active') is not False,
                    **_stamps(row),
                )
            )
            self.count('options')
        for row in self.data['survey_question_scale_ranges']:
            if await self._exists(ScaleRange, int(row['id'])):
                continue
            self.session.add(
                ScaleRange(
                    id=int(row['id']),
                    question_id=int(row['question_id']),
                    title=_text(row.get('title'), 255),
                    from_value=float(row.get('from_value') or 0),
                    to_value=float(row.get('to_value') or 0),
                    order=_int(row.get('order')) or 0,
                    **_stamps(row),
                )
            )
            self.count('scale_ranges')
        await self.session.flush()

        for row in self.data['survey_publishings']:
            if await self._exists(Publishing, int(row['id'])):
                continue
            publishing = Publishing(
                id=int(row['id']),
                survey_id=int(row['survey_id']),
                title=_text(row.get('title'), 500) or 'Публикация',
                public_token=_text(row.get('public_token'), 64),
                is_active=row.get('is_active') is not False,
                is_anonymous=row.get('is_anonymous') is not False,
                created_by_id=owner.id if owner else None,
                **_stamps(row),
            )
            observers = [await self.person_user(nb_id) for nb_id in _ids(row.get('observers'))]
            publishing.observers = [u for u in observers if u is not None]
            self.session.add(publishing)
            self.count('publishings')
        await self.session.flush()

        for row in self.data['survey_responses']:
            if await self._exists(Response, int(row['id'])):
                continue
            token = _text(row.get('token'))
            if not token:
                self.skip('responses', row['id'], 'нет ключа прохождения')
                continue
            submitted = row.get('status') == STATUS_SUBMITTED
            self.session.add(
                Response(
                    id=int(row['id']),
                    publishing_id=int(row['publishing_id']),
                    token_hash=hash_secret(token),
                    status=STATUS_SUBMITTED if submitted else STATUS_IN_PROGRESS,
                    submitted_at=_dt(row.get('submitted_at')) if submitted else None,
                    **_stamps(row),
                )
            )
            self.count('responses')
        await self.session.flush()

        options = {o.id: o for o in await self.session.scalars(select(Option))}
        responses = set(await self.session.scalars(select(Response.id)))
        questions = set(await self.session.scalars(select(Question.id)))
        for row in self.data['survey_answers']:
            if await self._exists(Answer, int(row['id'])):
                continue
            if int(row['response_id']) not in responses or int(row['question_id']) not in questions:
                self.skip('answers', row['id'], 'нет прохождения или вопроса')
                continue
            answer = Answer(
                id=int(row['id']),
                response_id=int(row['response_id']),
                question_id=int(row['question_id']),
                text_value=row.get('text_value') or None,
                rich_text_value=nh3.clean(row['rich_text_value'], tags=RICH_TEXT_TAGS)
                if row.get('rich_text_value')
                else None,
                number_value=row.get('number_value'),
                boolean_value=row.get('boolean_value'),
                scale_item_id=_int(row.get('scale_item_id')),
                option_id=_int(row.get('option_id')),
                is_skipped=bool(row.get('is_skipped')),
                **_stamps(row),
            )
            answer.selected_options = [options[i] for i in _ids(row.get('options')) if i in options]
            self.session.add(answer)
            self.count('answers')
        await self.session.flush()

        answers = set(await self.session.scalars(select(Answer.id)))
        for row in self.data['survey_answer_ranking_items']:
            if await self._exists(RankingItem, int(row['id'])):
                continue
            if int(row['answer_id']) not in answers or int(row['option_id']) not in options:
                self.skip('ranking', row['id'], 'нет ответа или варианта')
                continue
            self.session.add(
                RankingItem(
                    id=int(row['id']),
                    answer_id=int(row['answer_id']),
                    option_id=int(row['option_id']),
                    rank=_int(row.get('rank')) or 0,
                    **_stamps(row),
                )
            )
            self.count('ranking_items')
        await self.session.flush()
        return {'counts': self.counts, 'skipped': self.skipped}


async def load(session: AsyncSession, source: Path, owner_email: str | None = None) -> dict:
    """Загрузка выгрузки. owner_email - владелец перенесённых опросов в конструкторе."""
    report = await Loader(session, source).run(owner_email)
    (source / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report

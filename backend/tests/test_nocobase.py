"""Перенос из NocoBase: ID и ссылки сохраняются, ключи прохождений работают, повторная загрузка не дублирует."""

import json

import pytest
from sqlalchemy import func, select

from app.legacy.nocobase import load
from app.modules.responses.models import Answer, Response
from app.modules.surveys.models import Publishing

pytestmark = pytest.mark.usefixtures('redis_clean')

STAMP = {'createdAt': '2026-04-07T09:19:14.706+00:00', 'updatedAt': '2026-04-07T09:20:00+00:00'}
DATA = {
    'persons': [{'id': 9, 'last_name': 'Дементьева', 'first_name': 'Виктория', 'email': 'vd@example.org'}],
    'surveys': [
        {'id': 100, 'title': 'Пульс', 'code': 'pulse', 'is_active': True, 'thank_you_text': 'Спасибо', **STAMP}
    ],
    'survey_sections': [{'id': 110, 'survey_id': 100, 'title': 'Работа', 'order': 1, 'is_active': True, **STAMP}],
    'survey_scales': [
        {'id': 120, 'title': '1–10', 'scale_type': 'generated', 'min_value': 1, 'max_value': 10, 'step': 1}
    ],
    'survey_questions': [
        {'id': 130, 'survey_id': 100, 'section_id': 110, 'text': 'Оценка', 'question_type': 'scale', 'scale_id': 120},
        {'id': 131, 'survey_id': 100, 'text': 'Что важно', 'question_type': 'multiple_choice', 'max_selections': 2},
        {'id': 132, 'survey_id': 100, 'text': 'Порядок', 'question_type': 'ranking'},
    ],
    'survey_question_options': [
        {'id': 140, 'question_id': 131, 'title': 'Коллеги', 'order': 1},
        {'id': 141, 'question_id': 131, 'title': 'Зарплата', 'order': 2},
        {'id': 142, 'question_id': 132, 'title': 'А', 'order': 1},
        {'id': 143, 'question_id': 132, 'title': 'Б', 'order': 2},
    ],
    'survey_question_scale_ranges': [
        {'id': 150, 'question_id': 130, 'title': 'Высокая', 'from_value': 8, 'to_value': 10}
    ],
    'survey_publishings': [
        {'id': 160, 'survey_id': 100, 'title': 'Весна', 'public_token': 'xbq8iau0', 'observers': [{'id': 9}], **STAMP}
    ],
    'survey_responses': [
        {'id': 170, 'publishing_id': 160, 'token': 'old-submitted-token', 'status': 'submitted', **STAMP},
        {'id': 171, 'publishing_id': 160, 'token': 'old-draft-token', 'status': 'in_progress', **STAMP},
    ],
    'survey_answers': [
        {'id': 180, 'response_id': 170, 'question_id': 130, 'number_value': 9},
        {'id': 181, 'response_id': 170, 'question_id': 131, 'options': [{'id': 140}, {'id': 141}]},
        {'id': 182, 'response_id': 170, 'question_id': 132},
    ],
    'survey_answer_ranking_items': [
        {'id': 190, 'answer_id': 182, 'option_id': 143, 'rank': 1},
        {'id': 191, 'answer_id': 182, 'option_id': 142, 'rank': 2},
    ],
}


@pytest.fixture
def source(tmp_path):
    for name, rows in DATA.items():
        (tmp_path / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False))
    return tmp_path


async def test_load_and_reuse_old_links(db, client, source):
    report = await load(db, source, 'owner@example.org')
    await db.commit()
    assert report['skipped'] == {}
    assert report['counts']['answers'] == 3 and report['counts']['ranking_items'] == 2

    public = (await client.get('/api/v1/public/s/xbq8iau0')).json()
    assert [q['id'] for q in public['questions']] == [130, 131, 132]

    # Незаконченное прохождение продолжается старым ключом
    headers = {'X-Response-Token': 'old-draft-token'}
    state = await client.get('/api/v1/public/responses/current', headers=headers)
    assert state.status_code == 200 and state.json()['response_id'] == 171
    answer = await client.put('/api/v1/public/responses/current/answers/130', json={'number_value': 7}, headers=headers)
    assert answer.status_code == 200

    response = await db.get(Response, 170)
    assert response.token_hash != 'old-submitted-token'
    multi = await db.get(Answer, 181)
    await db.refresh(multi, ['selected_options', 'ranking'])
    assert sorted(multi.option_ids) == [140, 141]
    publishing = await db.get(Publishing, 160)
    assert [u.email for u in publishing.observers] == ['vd@example.org']

    again = await load(db, source, 'owner@example.org')
    await db.commit()
    assert again['counts'] == {}
    assert await db.scalar(select(func.count(Answer.id))) == 4

from io import BytesIO

import pytest
from openpyxl import load_workbook

from tests.conftest import other_client
from tests.helpers import login_employee

pytestmark = pytest.mark.usefixtures('redis_clean')


@pytest.mark.parametrize('kind', ['matrix_single', 'matrix_multiple'])
async def test_matrix_roundtrip(db, client, kind):
    await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Сравнение модулей'})).json()
    url = f'/api/v1/surveys/{survey["id"]}'
    body = {
        'text': 'Что изменилось?',
        'question_type': kind,
        'is_required': True,
        'matrix_rows': [{'id': 'schedule', 'title': 'Расписание'}, {'id': 'meetings', 'title': 'Встречи'}],
        'options': [
            {'title': 'Лучше'},
            {'title': 'Без изменений'},
            {'title': 'Не могу сравнить', 'exclude_from_base': True},
        ],
    }
    assert (await client.post(f'{url}/publishings', json={'title': 'Проверка'})).status_code == 400
    question_response = await client.post(f'{url}/questions', json=body)
    assert question_response.status_code == 201, question_response.text
    question = question_response.json()
    better, same, excluded = [o['id'] for o in question['options']]

    copy = (await client.post(f'{url}/copy')).json()['questions'][0]
    assert copy['matrix_rows'] == body['matrix_rows']
    assert copy['options'][2]['exclude_from_base'] is True
    assert copy['options'][2]['id'] != excluded

    preview = (await client.get(f'{url}/preview')).json()
    assert preview['questions'][0]['matrix_rows'] == body['matrix_rows']
    assert (await client.get(f'{url}/publishings')).json() == []
    publishing = (await client.post(f'{url}/publishings', json={'title': 'Проверка'})).json()
    answers_url = '/api/v1/public/responses/current/answers'
    submit_url = '/api/v1/public/responses/current/submit'
    token = publishing['public_token']

    async with other_client(client) as guest:
        assert (await guest.get(f'{url}/preview')).status_code == 401
        first_row = [better, same, excluded] if kind == 'matrix_multiple' else [better]
        for index, schedule in enumerate([first_row, [same], [excluded]]):
            started = (await guest.post(f'/api/v1/public/s/{token}/responses')).json()
            headers = {'X-Response-Token': started['response_token']}

            async def save(choices, headers=headers):
                return await guest.put(
                    f'{answers_url}/{question["id"]}', json={'matrix_choices': choices}, headers=headers
                )

            if index == 0:
                assert (await save({'unknown': [better]})).status_code == 400
                assert (await save({'schedule': [copy['options'][0]['id']]})).status_code == 400
                if kind == 'matrix_single':
                    assert (await save({'schedule': [better, same]})).status_code == 400
                assert (await save({'schedule': schedule})).status_code == 200
                missing = await guest.post(submit_url, headers=headers)
                assert missing.json()['detail']['question_ids'] == [question['id']]

            choices = {'schedule': schedule, 'meetings': [excluded]}
            assert (await save(choices)).status_code == 200
            state = (await guest.get('/api/v1/public/responses/current', headers=headers)).json()
            assert state['answers'][0]['matrix_choices'] == choices
            assert (await guest.post(submit_url, headers=headers)).status_code == 200

    pub_url = f'/api/v1/publishings/{publishing["id"]}'
    result = (await client.get(f'{pub_url}/results')).json()['questions'][0]['matrix_rows']
    schedule, meetings = result
    assert schedule['base'] == 2 and schedule['answered'] == 3
    assert schedule['options'][0]['percent'] == 50
    assert schedule['options'][1]['percent'] == (100 if kind == 'matrix_multiple' else 50)
    assert schedule['excluded'][0]['percent'] == (66.7 if kind == 'matrix_multiple' else 33.3)
    assert meetings['base'] == 0 and meetings['excluded'][0]['percent'] == 100

    book = load_workbook(BytesIO((await client.get(f'{pub_url}/export.xlsx')).content))
    rows = list(book['Ответы'].values)
    assert rows[0][:3] == ('№', 'Что изменилось? / Расписание', 'Что изменилось? / Встречи')
    assert rows[-1][1:3] == ('Не могу сравнить', 'Не могу сравнить')
    assert ('', 'Лучше', 1, 50, 2, 'Сравнимые ответы') in [(row[0] or '', *row[1:6]) for row in book['Сводка'].values]
    changed = {**question, 'matrix_rows': body['matrix_rows'][:1]}
    assert (await client.put(f'/api/v1/questions/{question["id"]}', json=changed)).status_code == 409


async def test_publishing_period_and_separate_start_limits(db, client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'responses_per_ip_hour', 1)
    await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).json()
    url = f'/api/v1/surveys/{survey["id"]}'
    await client.post(f'{url}/questions', json={'text': 'Что изменилось?', 'question_type': 'text'})
    future = {'opens_at': '2099-01-01T12:00:00Z', 'closes_at': '2099-01-01T15:00:00Z'}
    scheduled = (await client.post(f'{url}/publishings', json={'title': 'Запланирована', **future})).json()
    assert scheduled['status'] == 'scheduled'
    invalid = await client.patch(f'/api/v1/publishings/{scheduled["id"]}', json={'closes_at': '2099-01-01T11:00:00Z'})
    assert invalid.status_code == 400

    first = (await client.post(f'{url}/publishings', json={'title': 'Первая'})).json()
    second = (await client.post(f'{url}/publishings', json={'title': 'Вторая'})).json()
    async with other_client(client) as guest:
        for publishing, expected in ((first, 201), (first, 429), (second, 201)):
            started = await guest.post(f'/api/v1/public/s/{publishing["public_token"]}/responses')
            assert started.status_code == expected

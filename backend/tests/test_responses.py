"""Прохождение по публичной ссылке: ключ прохождения, проверки ответов, отправка, неанонимные опросы."""

from datetime import timedelta

import pytest
from sk_common.security import now_utc
from sk_common.testing import login_as

from tests.conftest import other_client
from tests.helpers import build_survey, full_answers, login_employee

pytestmark = pytest.mark.usefixtures('redis_clean')

ANSWER = '/api/v1/public/responses/current/answers/{}'
SUBMIT = '/api/v1/public/responses/current/submit'


async def _start(client, token):
    response = await client.post(f'/api/v1/public/s/{token}/responses')
    assert response.status_code == 201, response.text
    return {'X-Response-Token': response.json()['response_token']}


async def test_public_survey_and_full_pass(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    token = built['publishing']['public_token']
    async with other_client(client) as guest:
        public = (await guest.get(f'/api/v1/public/s/{token}')).json()
        assert public['requires_login'] is False and len(public['questions']) == 8
        assert public['scales'][0]['max_value'] == 10
        assert 'score' not in public['questions'][2]['options'][0]

        headers = await _start(guest, token)
        for kind, value in full_answers(built['questions']).items():
            saved = await guest.put(ANSWER.format(built['questions'][kind]['id']), json=value, headers=headers)
            assert saved.status_code == 200, (kind, saved.text)
        state = (await guest.get('/api/v1/public/responses/current', headers=headers)).json()
        rich = next(a for a in state['answers'] if a['rich_text_value'])
        assert '<script>' not in rich['rich_text_value'] and '<b>жирный</b>' in rich['rich_text_value']

        submitted = await guest.post(SUBMIT, headers=headers)
        assert submitted.json() == {'status': 'submitted', 'thank_you_text': 'Спасибо!'}
        again = await guest.put(ANSWER.format(built['questions']['text']['id']), json={}, headers=headers)
        assert again.status_code == 409


async def test_response_token_is_required(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    question = built['questions']['text']['id']
    await _start(client, built['publishing']['public_token'])
    assert (await client.put(ANSWER.format(question), json={'text_value': 'x'})).status_code == 401
    wrong = {'X-Response-Token': 'not-my-token-at-all'}
    assert (await client.put(ANSWER.format(question), json={'text_value': 'x'}, headers=wrong)).status_code == 401
    assert (await client.post(SUBMIT, headers=wrong)).status_code == 401


@pytest.mark.parametrize(
    'kind, value',
    [
        ('single_choice', {'option_id': 1}),
        ('multiple_choice', {'option_ids': 'all'}),
        ('number', {'number_value': 101}),
        ('scale', {'number_value': 11}),
        ('scale', {'number_value': 2.5}),
        ('ranking', {'ranking': 'duplicate'}),
    ],
)
async def test_invalid_answers(db, client, kind, value):
    await login_employee(db, client)
    built = await build_survey(client)
    question = built['questions'][kind]
    option_ids = [o['id'] for o in question['options']]
    if value.get('option_ids') == 'all':
        value = {'option_ids': option_ids}  # больше max_selections=2
    if value.get('ranking') == 'duplicate':
        value = {'ranking': [option_ids[0], option_ids[0]]}
    headers = await _start(client, built['publishing']['public_token'])
    assert (await client.put(ANSWER.format(question['id']), json=value, headers=headers)).status_code == 400


async def test_required_questions_block_submit(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    headers = await _start(client, built['publishing']['public_token'])
    await client.put(ANSWER.format(built['questions']['text']['id']), json={'text_value': 'Ответ'}, headers=headers)
    # Необязательный вопрос можно пропустить, обязательный — нет
    skip = await client.put(
        ANSWER.format(built['questions']['yes_no']['id']), json={'is_skipped': True}, headers=headers
    )
    assert skip.json()['is_skipped'] is True
    response = await client.post(SUBMIT, headers=headers)
    assert response.status_code == 400
    assert response.json()['detail']['question_ids'] == [built['questions']['single_choice']['id']]


async def test_closed_and_inactive_publishing(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    pid, token = built['publishing']['id'], built['publishing']['public_token']
    closed = (now_utc() - timedelta(days=1)).isoformat()
    await client.patch(f'/api/v1/publishings/{pid}', json={'closes_at': closed})
    assert (await client.get(f'/api/v1/public/s/{token}')).status_code == 410
    await client.patch(f'/api/v1/publishings/{pid}', json={'closes_at': None, 'is_active': False})
    assert (await client.get(f'/api/v1/public/s/{token}')).status_code == 404
    assert (await client.get('/api/v1/public/s/unknown')).status_code == 404


async def test_personal_publishing_needs_login_and_keeps_one_response(db, client):
    await login_employee(db, client)
    built = await build_survey(client, anonymous=False)
    token = built['publishing']['public_token']
    async with other_client(client) as student:
        public = (await student.get(f'/api/v1/public/s/{token}')).json()
        assert public['requires_login'] is True and public['questions'] == []
        assert (await student.post(f'/api/v1/public/s/{token}/responses')).status_code == 401

        await login_as(db, student, email='anna@example.org', last_name='Иванова')
        first = (await student.post(f'/api/v1/public/s/{token}/responses')).json()
        headers = {'X-Response-Token': first['response_token']}
        await student.put(ANSWER.format(built['questions']['text']['id']), json={'text_value': 'Да'}, headers=headers)

        # С другого устройства — то же прохождение с сохранёнными ответами, старый ключ больше не действует
        second = (await student.post(f'/api/v1/public/s/{token}/responses')).json()
        assert second['response_id'] == first['response_id'] and len(second['answers']) == 1
        assert (await student.get('/api/v1/public/responses/current', headers=headers)).status_code == 401

"""Сводка и выгрузка результатов, доступ к ним."""

from io import BytesIO

import pytest
from openpyxl import load_workbook

from tests.conftest import other_client
from tests.helpers import build_survey, full_answers, login_employee

pytestmark = pytest.mark.usefixtures('redis_clean')


async def _answer(client, built, overrides=None, submit=True):
    token = built['publishing']['public_token']
    started = (await client.post(f'/api/v1/public/s/{token}/responses')).json()
    headers = {'X-Response-Token': started['response_token']}
    for kind, value in {**full_answers(built['questions']), **(overrides or {})}.items():
        response = await client.put(
            f'/api/v1/public/responses/current/answers/{built["questions"][kind]["id"]}', json=value, headers=headers
        )
        assert response.status_code == 200, response.text
    if submit:
        assert (await client.post('/api/v1/public/responses/current/submit', headers=headers)).status_code == 200


async def test_summary(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    opts = {kind: [o['id'] for o in q['options']] for kind, q in built['questions'].items()}
    async with other_client(client) as guest:
        await _answer(guest, built)
        await _answer(
            guest, built, {'scale': {'number_value': 2}, 'single_choice': {'option_id': opts['single_choice'][1]}}
        )
        await _answer(guest, built, submit=False)

    results = (await client.get(f'/api/v1/publishings/{built["publishing"]["id"]}/results')).json()
    assert results['responses'] == 2 and results['in_progress'] == 0
    by_type = {q['question_type']: q for q in results['questions']}

    single = by_type['single_choice']
    assert [(o['count'], o['percent']) for o in single['options']] == [(1, 50.0), (1, 50.0), (0, 0.0)]
    scale = by_type['scale']
    assert scale['mean'] == 5 and scale['min'] == 2 and scale['max'] == 8
    assert len(scale['distribution']) == 10
    assert [(r['title'], r['count']) for r in scale['ranges']] == [('Низкая', 1), ('Средняя', 0), ('Высокая', 1)]
    ranking = by_type['ranking']['ranking']
    assert ranking[0]['id'] == opts['ranking'][-1] and ranking[0]['first_places'] == 2
    assert by_type['yes_no']['options'][0] == {'id': None, 'title': 'Да', 'count': 2, 'percent': 100.0}
    assert [t['text'] for t in by_type['text']['texts']] == ['Всё хорошо', 'Всё хорошо']

    with_drafts = (
        await client.get(
            f'/api/v1/publishings/{built["publishing"]["id"]}/results', params={'include_in_progress': True}
        )
    ).json()
    assert with_drafts['in_progress'] == 1


async def test_export_xlsx(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    async with other_client(client) as guest:
        await _answer(guest, built)
    response = await client.get(f'/api/v1/publishings/{built["publishing"]["id"]}/export.xlsx')
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    rows = list(book['Ответы'].values)
    assert rows[0][:2] == ('№', 'Вопрос text')
    assert rows[1][1] == 'Всё хорошо' and rows[1][5] == '42' and rows[1][6] == 'Да'
    assert 'Сводка' in book.sheetnames


async def test_results_access(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    url = f'/api/v1/publishings/{built["publishing"]["id"]}/results'
    async with other_client(client) as stranger:
        assert (await stranger.get(url)).status_code == 401
        await login_employee(db, stranger, email='other@skolkovo.example.org', last_name='Другой')
        assert (await stranger.get(url)).status_code == 404
        await client.patch(
            f'/api/v1/publishings/{built["publishing"]["id"]}',
            json={'observer_person_ids': [(await _person_id(db, 'other@skolkovo.example.org'))]},
        )
        assert (await stranger.get(url)).status_code == 200


async def _person_id(db, email):
    from sk_common.people.models import User
    from sqlalchemy import select

    return await db.scalar(select(User.person_id).where(User.email == email))

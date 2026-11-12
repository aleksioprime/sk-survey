from io import BytesIO

import pytest
from openpyxl import load_workbook

from tests.conftest import other_client
from tests.helpers import login_employee

pytestmark = pytest.mark.usefixtures('redis_clean')


@pytest.mark.parametrize('required', [False, True])
async def test_text_list_limits_draft_and_export(db, client, required):
    await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Проекты'})).json()
    survey_url = f'/api/v1/surveys/{survey["id"]}'
    config = {
        'question_type': 'text_list',
        'text': 'Перечислите проекты',
        'is_required': required,
        'min_rows': 2,
        'max_rows': 3,
    }
    assert (await client.post(f'{survey_url}/questions', json={**config, 'max_rows': 1})).status_code == 422
    created = await client.post(f'{survey_url}/questions', json=config)
    assert created.status_code == 201, created.text
    question_id = created.json()['id']
    copied = (await client.post(f'{survey_url}/copy')).json()['questions'][0]
    assert (copied['min_rows'], copied['max_rows']) == (2, 3)

    publication = (await client.post(f'{survey_url}/publishings', json={'title': 'Для проверки'})).json()
    link = f'/api/v1/public/s/{publication["public_token"]}'
    current = '/api/v1/public/responses/current'
    async with other_client(client) as guest:
        form = (await guest.get(link)).json()['questions'][0]
        assert (form['min_rows'], form['max_rows']) == (2, 3)

        async def begin():
            return {'X-Response-Token': (await guest.post(f'{link}/responses')).json()['response_token']}

        headers = await begin()
        empty = await guest.post(f'{current}/submit', headers=headers)
        assert empty.status_code == (400 if required else 200)
        if not required:
            headers = await begin()

        answer_url = f'{current}/answers/{question_id}'
        draft = await guest.put(answer_url, json={'text_rows': ['  Библиотека  ', ' \t ']}, headers=headers)
        assert draft.status_code == 200 and draft.json()['text_rows'] == ['Библиотека']
        incomplete = await guest.post(f'{current}/submit', headers=headers)
        assert incomplete.status_code == 400
        assert incomplete.json()['detail']['question_errors'][str(question_id)] == 'Минимум заполненных строк: 2'

        over = await guest.put(answer_url, json={'text_rows': ['А', 'Б', 'В', 'Г']}, headers=headers)
        assert over.status_code == 400
        state = (await guest.get(current, headers=headers)).json()
        assert state['answers'][0]['text_rows'] == ['Библиотека']

        ready = await guest.put(answer_url, json={'text_rows': ['=1+1', '', '  Мастерская  ']}, headers=headers)
        assert ready.status_code == 200 and ready.json()['text_rows'] == ['=1+1', 'Мастерская']
        assert (await guest.post(f'{current}/submit', headers=headers)).status_code == 200

    publishing_url = f'/api/v1/publishings/{publication["id"]}'
    results = (await client.get(f'{publishing_url}/results')).json()['questions'][0]
    assert results['answered'] == 1 and results['texts'][0]['text'] == '=1+1\nМастерская'
    export = await client.get(f'{publishing_url}/export.xlsx')
    assert export.status_code == 200
    sheet = load_workbook(BytesIO(export.content))['Ответы']
    cell = sheet.cell(row=sheet.max_row, column=2)
    assert cell.value == '=1+1\nМастерская'
    assert cell.data_type == 's' and cell.alignment.wrap_text

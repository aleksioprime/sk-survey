"""Сводка и выгрузка результатов, доступ к ним."""

from datetime import date, datetime
from io import BytesIO

import pytest
from docx import Document
from openpyxl import load_workbook

from app.modules.results import service
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
    return headers


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
    assert single['is_required'] == built['questions']['single_choice']['is_required']
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
    long_text = '=1+1\n' + 'Длинный ответ с переносом по словам. ' * 15
    async with other_client(client) as guest:
        await _answer(guest, built, {'text': {'text_value': long_text.strip()}})
        await _answer(guest, built)
    response = await client.get(f'/api/v1/publishings/{built["publishing"]["id"]}/export.xlsx')
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.content))
    rows = list(book['Ответы'].values)
    assert rows[0][:2] == ('№', 'Вопрос text')
    assert rows[1][1] == long_text.strip() and rows[1][5] == '42' and rows[1][6] == 'Да'
    assert rows[1][2] == 'Ок жирный'
    sheet = book['Ответы']
    assert sheet['B2'].data_type == 's' and sheet['B2'].alignment.wrap_text
    assert sheet.column_dimensions['A'].width < sheet.column_dimensions['B'].width <= 64
    assert sheet.row_dimensions[2].height > sheet.row_dimensions[3].height
    assert book['Сводка']['A1'].alignment.wrap_text
    assert book['Сводка'].column_dimensions['A'].width > book['Сводка'].column_dimensions['D'].width
    assert rows[0][-2:] == ('Начало попытки (МСК)', 'Отправлен (МСК)')
    assert isinstance(rows[1][-2], datetime) and rows[1][-2] <= rows[1][-1]
    summary = list(book['Сводка'].values)
    assert summary[0][-1] == 'Обязательность'
    assert summary[1][-1] in ('Обязательный', 'Необязательный')


async def test_export_individual_docx(db, client):
    user = await login_employee(db, client)
    built = await build_survey(client, anonymous=False)
    await _answer(client, built)
    publication = f'/api/v1/publishings/{built["publishing"]["id"]}'
    (item,) = (await client.get(f'{publication}/responses')).json()['items']
    path = f'/responses/{item["id"]}/export.docx'
    other = await build_survey(client)
    assert (await client.get(f'/api/v1/publishings/{other["publishing"]["id"]}{path}')).status_code == 404
    async with other_client(client) as observer:
        assert (await observer.get(publication + path)).status_code == 401
        reader = await login_employee(db, observer, email='reader@skolkovo.example.org')
        assert (await observer.get(publication + path)).status_code == 404
        await client.patch(publication, json={'observer_person_ids': [reader.person_id]})
        download = await observer.get(publication + path)
    assert download.status_code == 200
    assert download.headers['Content-Disposition'].endswith('.docx')
    assert download.headers['Content-Type'].endswith('wordprocessingml.document')
    text = '\n'.join(p.text for p in Document(BytesIO(download.content)).paragraphs)
    for expected in [
        'Пульс-опрос',
        'Весна',
        'Работа',
        user.person.full_name,
        'Статус: Отправлен',
        '1. Вопрос text',
        'Всё хорошо',
        'Ок жирный',
        '1. Нет',
        'Да, полностью',
    ]:
        assert expected in text

    async with other_client(client) as guest:
        await _answer(guest, other)
        started = await guest.post(f'/api/v1/public/s/{other["publishing"]["public_token"]}/responses')
        assert started.status_code == 201
    url = f'/api/v1/publishings/{other["publishing"]["id"]}/responses'
    draft = (await client.get(url, params={'include_in_progress': True})).json()['items'][-1]
    download = await client.get(f'{url}/{draft["id"]}/export.docx')
    text = '\n'.join(p.text for p in Document(BytesIO(download.content)).paragraphs)
    assert 'Анонимный ответ' in text and 'Статус: Не отправлен' in text and 'Нет ответа' in text
    assert user.person.full_name not in text and 'Всё хорошо' not in text


async def test_date_and_short_text_from_survey_to_export(db, client):
    await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Анкета сотрудника'})).json()
    base = f'/api/v1/surveys/{survey["id"]}'
    question_ids = []
    for kind, label in [('date', 'Дата выхода на работу'), ('short_text', 'Должность')]:
        response = await client.post(
            f'{base}/questions', json={'question_type': kind, 'text': label, 'is_required': True}
        )
        assert response.status_code == 201, response.text
        question_ids.append(response.json()['id'])
    publishing = (await client.post(f'{base}/publishings', json={'title': 'Адаптация'})).json()
    url = f'/api/v1/publishings/{publishing["id"]}'

    async with other_client(client) as guest:
        public = f'/api/v1/public/s/{publishing["public_token"]}'
        form = (await guest.get(public)).json()
        assert [q['question_type'] for q in form['questions']] == ['date', 'short_text']
        started = (await guest.post(f'{public}/responses')).json()
        headers = {'X-Response-Token': started['response_token']}
        current = '/api/v1/public/responses/current'
        date_url, short_url = [f'{current}/answers/{qid}' for qid in question_ids]

        for invalid in ('2025-02-29', '2024-02-29T00:00:00', 1709164800):
            assert (await guest.put(date_url, json={'date_value': invalid}, headers=headers)).status_code == 422
        assert (await guest.put(short_url, json={'text_value': 'Первая\nВторая'}, headers=headers)).status_code == 400
        assert (await guest.put(short_url, json={'text_value': 'Учитель'}, headers=headers)).status_code == 200
        incomplete = await guest.post(f'{current}/submit', headers=headers)
        assert incomplete.json()['detail']['question_ids'] == [question_ids[0]]

        valid = '2024-02-29'
        assert (await guest.put(date_url, json={'date_value': valid}, headers=headers)).status_code == 200
        state = (await guest.get(current, headers=headers)).json()
        restored = {answer['question_id']: answer for answer in state['answers']}
        assert restored[question_ids[0]]['date_value'] == valid
        assert (await guest.post(f'{current}/submit', headers=headers)).status_code == 200

    results = (await client.get(f'{url}/results')).json()
    assert [q['texts'][0]['text'] for q in results['questions']] == [valid, 'Учитель']
    responses = (await client.get(f'{url}/responses')).json()
    assert [a['text'] for a in responses['items'][0]['answers']] == [valid, 'Учитель']
    export = await client.get(f'{url}/export.xlsx')
    book = load_workbook(BytesIO(export.content))
    assert list(book['Ответы'].values)[1][1:3] == (date(2024, 2, 29), 'Учитель')


async def test_individual_responses(db, client, monkeypatch):
    monkeypatch.setattr(service, 'RESPONSES_PER_PAGE', 1)
    await login_employee(db, client)
    built = await build_survey(client)
    async with other_client(client) as guest:
        await _answer(guest, built)
        await _answer(guest, built, {'text': {'text_value': 'Черновик'}}, submit=False)

    url = f'/api/v1/publishings/{built["publishing"]["id"]}/responses'
    page = (await client.get(url)).json()
    assert (page['page'], page['responses'], page['in_progress']) == (1, 1, 0)
    answer = page['items'][0]
    assert set(answer) == {
        'id',
        'publishing_id',
        'number',
        'submitted',
        'started_at',
        'submitted_at',
        'respondent',
        'study_class',
        'answers',
    }
    assert answer['id'].isdigit()
    assert answer['submitted']
    assert datetime.fromisoformat(answer['started_at']) <= datetime.fromisoformat(answer['submitted_at'])
    assert answer['respondent'] is None and answer['study_class'] is None
    assert {item['question']: item['text'] for item in answer['answers']}['Вопрос text'] == 'Всё хорошо'

    with_draft = (await client.get(url, params={'include_in_progress': True, 'page': 2})).json()
    assert (with_draft['page'], with_draft['responses'], with_draft['in_progress']) == (2, 1, 1)
    draft = with_draft['items'][0]
    assert draft['number'] == 2 and not draft['submitted']
    assert draft['started_at'] and draft['submitted_at'] is None
    assert {item['question']: item['text'] for item in draft['answers']}['Вопрос text'] == 'Черновик'


async def test_results_access(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    base_url = f'/api/v1/publishings/{built["publishing"]["id"]}'
    other = await build_survey(client)
    other_url = f'/api/v1/publishings/{other["publishing"]["id"]}/responses'
    async with other_client(client) as stranger:
        assert (await stranger.get(f'{base_url}/results')).status_code == 401
        assert (await stranger.get(f'{base_url}/responses')).status_code == 401
        await login_employee(db, stranger, email='other@skolkovo.example.org', last_name='Другой')
        assert (await stranger.get(f'{base_url}/results')).status_code == 404
        assert (await stranger.get(f'{base_url}/responses')).status_code == 404
        await client.patch(
            base_url,
            json={'observer_person_ids': [(await _person_id(db, 'other@skolkovo.example.org'))]},
        )
        assert (await stranger.get(f'{base_url}/results')).status_code == 200
        assert (await stranger.get(f'{base_url}/responses')).status_code == 200
        assert (await stranger.get(other_url)).status_code == 404


async def test_delete_individual_response(db, client, monkeypatch):
    monkeypatch.setattr(service, 'RESPONSES_PER_PAGE', 1)
    await login_employee(db, client)
    built = await build_survey(client)
    other = await build_survey(client)
    url = f'/api/v1/publishings/{built["publishing"]["id"]}'
    other_url = f'/api/v1/publishings/{other["publishing"]["id"]}'
    async with other_client(client) as guest:
        headers = await _answer(guest, built)
        state = await guest.get('/api/v1/public/responses/current', headers=headers)
        assert state.json()['status'] == 'submitted'
        assert state.headers['Cache-Control'] == 'no-store'
        await _answer(guest, built, submit=False)
    page = (await client.get(f'{url}/responses')).json()
    response_id = page['items'][0]['id']
    response_url = f'{url}/responses/{response_id}'
    async with other_client(client) as observer:
        assert (await observer.delete(response_url)).status_code == 401
        await login_employee(db, observer, email='observer@skolkovo.example.org')
        update = await client.patch(
            url, json={'observer_person_ids': [await _person_id(db, 'observer@skolkovo.example.org')]}
        )
        assert update.status_code == 200
        assert (await observer.get(f'{url}/responses')).status_code == 200
        assert (await observer.delete(response_url)).status_code == 403

    assert (await client.delete(f'{other_url}/responses/{response_id}')).status_code == 404
    assert (await client.delete(response_url)).status_code == 204
    assert (await client.delete(response_url)).status_code == 404
    async with other_client(client) as guest:
        assert (await guest.get('/api/v1/public/responses/current', headers=headers)).status_code == 401
    summary = (await client.get(f'{url}/results')).json()
    assert summary['responses'] == 0 and all(q['answered'] == 0 for q in summary['questions'])
    remaining = (await client.get(f'{url}/responses', params={'include_in_progress': True, 'page': 2})).json()
    assert remaining['page'] == 1 and remaining['in_progress'] == 1 and not remaining['items'][0]['submitted']
    assert (await client.delete(f'{url}/responses/{remaining["items"][0]["id"]}')).status_code == 204


async def _person_id(db, email):
    from sk_common.people.models import User
    from sqlalchemy import select

    return await db.scalar(select(User.person_id).where(User.email == email))


async def test_combined_filtered_report(db, client, monkeypatch):
    user = await login_employee(db, client)
    built = await build_survey(client)
    publication = built['publishing']
    named = (
        await client.post(
            f'/api/v1/surveys/{built["survey"]["id"]}/publishings', json={'title': 'Осень', 'is_anonymous': False}
        )
    ).json()
    base = f'/api/v1/publishings/{publication["id"]}'
    q = built['questions']
    single = [o['id'] for o in q['single_choice']['options']]
    multiple = [o['id'] for o in q['multiple_choice']['options']]
    await _answer(
        client,
        {**built, 'publishing': named},
        {'single_choice': {'option_id': single[1]}, 'scale': {'number_value': 2}},
    )
    async with other_client(client) as guest:
        await _answer(guest, built)
        await _answer(guest, built, {'multiple_choice': {'option_ids': [multiple[2]]}})
        await _answer(guest, built, {'single_choice': {'option_id': single[2]}})
        await _answer(guest, built, submit=False)

    catalog = (await client.get(f'{base}/report-options')).json()
    assert {p['id'] for p in catalog['publications']} == {str(publication['id']), str(named['id'])}
    assert {i['id'] for i in catalog['questions']} == {str(q[k]['id']) for k in ('single_choice', 'multiple_choice')}
    params = {'publication': [named['id'], named['id']], 'option': [*single[:2], *multiple[:2]]}
    result = (await client.get(f'{base}/results', params=params)).json()
    assert result['responses'] == 2 and result['in_progress'] == 0
    assert next(i for i in result['questions'] if i['question_type'] == 'scale')['mean'] == 5
    assert (await client.get(f'{base}/results', params={'publication': named['id']})).json()['responses'] == 4
    drafts = (await client.get(f'{base}/responses', params={**params, 'include_in_progress': True})).json()
    assert drafts['responses'] == 2 and drafts['in_progress'] == 1
    assert [i['respondent'] for i in drafts['items']] == [user.person.full_name, None, None]
    assert drafts['items'][0]['publishing_id'] == str(named['id'])
    monkeypatch.setattr(service, 'RESPONSES_PER_PAGE', 1)
    last_page = (await client.get(f'{base}/responses', params={**params, 'page': 20})).json()
    assert (last_page['page'], last_page['responses']) == (2, 2)
    assert [item['id'] for item in last_page['items']] == [drafts['items'][1]['id']]

    book = load_workbook(BytesIO((await client.get(f'{base}/export.xlsx', params=params)).content))
    header, personal, anonymous = list(book['Ответы'].values)
    assert header[:2] == ('№', 'Публикация')
    assert personal[1] == 'Осень' and personal[header.index('ФИО')] == user.person.full_name
    assert anonymous[1] == publication['title'] and anonymous[header.index('Email')] is None
    assert any(row[1:3] == ('Среднее', 5) for row in book['Сводка'].values)
    empty = {'option': [single[2], multiple[2]]}
    assert (await client.get(f'{base}/results', params=empty)).json()['responses'] == 0
    sheet = load_workbook(BytesIO((await client.get(f'{base}/export.xlsx', params=empty)).content))['Ответы']
    assert sheet.max_row == 1

    other = await build_survey(client)
    for route in ('results', 'responses', 'export.xlsx'):
        assert (
            await client.get(f'{base}/{route}', params={'publication': other['publishing']['id']})
        ).status_code == 404
        assert (
            await client.get(f'{base}/{route}', params={'option': q['ranking']['options'][0]['id']})
        ).status_code == 422
    async with other_client(client) as observer:
        reader = await login_employee(db, observer, email='report-observer@skolkovo.example.org')
        await client.patch(base, json={'observer_person_ids': [reader.person_id]})
        visible = (await observer.get(f'{base}/report-options')).json()['publications']
        assert [p['id'] for p in visible] == [str(publication['id'])]
        for route in ('results', 'responses', 'export.xlsx'):
            assert (await observer.get(f'{base}/{route}', params=params)).status_code == 404

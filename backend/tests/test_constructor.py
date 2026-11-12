"""Конструктор: права, вопросы всех типов, варианты с ответами, порядок, копия, публикации."""

import pytest
from sk_common.people.models import Person
from sk_common.testing import login_as

from tests.conftest import other_client
from tests.helpers import build_survey, full_answers, login_employee

pytestmark = pytest.mark.usefixtures('redis_clean')


async def test_only_employees_create_surveys(db, client):
    await login_as(db, client, email='student@example.org')
    assert (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).status_code == 403
    assert (await client.get('/api/v1/auth/me')).json()['can_create_surveys'] is False


async def test_build_survey_with_all_question_types(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    survey = (await client.get(f'/api/v1/surveys/{built["survey"]["id"]}')).json()
    assert survey['role'] == 'owner'
    assert [q['question_type'] for q in survey['questions']] == list(built['questions'])
    assert [r['title'] for r in built['questions']['scale']['ranges']] == ['Низкая', 'Средняя', 'Высокая']
    assert built['publishing']['public_token'] and len(built['publishing']['public_token']) == 10


async def test_validation_of_question(db, client):
    await login_employee(db, client)
    sid = (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).json()['id']
    no_options = await client.post(
        f'/api/v1/surveys/{sid}/questions', json={'text': 'Выбор', 'question_type': 'single_choice'}
    )
    assert no_options.status_code == 422
    no_scale = await client.post(f'/api/v1/surveys/{sid}/questions', json={'text': 'Шкала', 'question_type': 'scale'})
    assert no_scale.status_code == 422


async def test_other_people_do_not_see_survey(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    async with other_client(client) as stranger:
        await login_employee(db, stranger, email='other@skolkovo.example.org', last_name='Другой')
        assert (await stranger.get(f'/api/v1/surveys/{built["survey"]["id"]}')).status_code == 404
        assert (await stranger.get('/api/v1/surveys')).json() == []


async def test_saved_editors_include_staff_without_prior_login(db, client):
    owner = await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).json()
    url = f'/api/v1/surveys/{survey["id"]}'
    first = Person(last_name='Первый', email='first-editor@example.org', is_employee=True)
    second = Person(last_name='Второй', email='second-editor@example.org', is_employee=True)
    db.add_all([first, second])
    await db.commit()

    def editor_ids(response):
        return {member['person_id'] for member in response.json()['members'] if member['role'] == 'editor'}

    assigned = await client.put(f'{url}/members', json={'editor_person_ids': [first.id]})
    assert assigned.status_code == 200
    assert editor_ids(assigned) == {first.id}

    rejected = await client.put(f'{url}/members', json={'editor_person_ids': [owner.person_id]})
    assert rejected.status_code == 400
    assert 'Владелец' in rejected.json()['detail']
    assert editor_ids(await client.get(url)) == {first.id}

    updated = await client.put(f'{url}/members', json={'editor_person_ids': [first.id, second.id]})
    assert updated.status_code == 200
    assert editor_ids(await client.get(url)) == {first.id, second.id}
    removed = await client.put(f'{url}/members', json={'editor_person_ids': [second.id]})
    assert removed.status_code == 200
    assert editor_ids(await client.get(url)) == {second.id}


async def test_editor_can_edit_but_not_delete(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    sid = built['survey']['id']
    async with other_client(client) as editor_client:
        editor = await login_employee(db, editor_client, email='editor@skolkovo.example.org', last_name='Редакторова')
        members = await client.put(f'/api/v1/surveys/{sid}/members', json={'editor_person_ids': [editor.person_id]})
        assert {m['role'] for m in members.json()['members']} == {'owner', 'editor'}
        assert (await editor_client.patch(f'/api/v1/surveys/{sid}', json={'title': 'Новое'})).status_code == 200
        assert (await editor_client.delete(f'/api/v1/surveys/{sid}')).status_code == 403


async def test_answered_options_are_kept_inactive(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    question = built['questions']['single_choice']
    token = built['publishing']['public_token']
    started = (await client.post(f'/api/v1/public/s/{token}/responses')).json()
    headers = {'X-Response-Token': started['response_token']}
    chosen = question['options'][2]['id']
    await client.put(
        f'/api/v1/public/responses/current/answers/{question["id"]}', json={'option_id': chosen}, headers=headers
    )

    # Убираем выбранный вариант и добавляем новый
    payload = {
        'text': question['text'],
        'question_type': 'single_choice',
        'options': [{'id': o['id'], 'title': o['title']} for o in question['options'][:2]] + [{'title': 'Другое'}],
    }
    updated = (await client.put(f'/api/v1/questions/{question["id"]}', json=payload)).json()
    by_title = {o['title']: o for o in updated['options']}
    assert by_title['Нет']['is_active'] is False and by_title['Другое']['is_active'] is True
    assert updated['answers_count'] == 1

    # Тип отвеченного вопроса менять нельзя, удалять — тоже
    payload['question_type'] = 'multiple_choice'
    assert (await client.put(f'/api/v1/questions/{question["id"]}', json=payload)).status_code == 409
    assert (await client.delete(f'/api/v1/questions/{question["id"]}')).status_code == 409


async def test_reorder_and_copy(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    sid = built['survey']['id']
    second = (await client.post(f'/api/v1/surveys/{sid}/sections', json={'title': 'Жизнь'})).json()
    ids = [q['id'] for q in built['questions'].values()]
    order = {
        'sections': [second['id'], built['section']['id']],
        'questions': [{'id': ids[-1], 'section_id': second['id']}] + [{'id': i, 'section_id': None} for i in ids[:-1]],
    }
    survey = (await client.put(f'/api/v1/surveys/{sid}/order', json=order)).json()
    assert [s['id'] for s in survey['sections']] == [second['id'], built['section']['id']]
    assert survey['questions'][0]['id'] == ids[-1] and survey['questions'][0]['section_id'] == second['id']

    copy = await client.post(f'/api/v1/surveys/{sid}/copy')
    assert copy.status_code == 201
    copied = copy.json()
    assert copied['title'] == 'Пульс-опрос (копия)'
    assert len(copied['questions']) == len(ids) and len(copied['sections']) == 2
    assert copied['questions'][0]['section_id'] != second['id']


async def test_cannot_delete_survey_with_answers(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    token = built['publishing']['public_token']
    started = (await client.post(f'/api/v1/public/s/{token}/responses')).json()
    headers = {'X-Response-Token': started['response_token']}
    for kind, value in full_answers(built['questions']).items():
        await client.put(
            f'/api/v1/public/responses/current/answers/{built["questions"][kind]["id"]}', json=value, headers=headers
        )
    assert (await client.post('/api/v1/public/responses/current/submit', headers=headers)).status_code == 200

    assert (await client.delete(f'/api/v1/surveys/{built["survey"]["id"]}')).status_code == 409
    assert (await client.delete(f'/api/v1/publishings/{built["publishing"]["id"]}')).status_code == 409
    listing = (await client.get('/api/v1/surveys')).json()
    assert listing[0]['responses_count'] == 1 and listing[0]['questions_count'] == 8


async def test_observers_from_directory(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    async with other_client(client) as observer_client:
        observer = await login_employee(db, observer_client, email='head@skolkovo.example.org', last_name='Завучева')
        found = (await client.get('/api/v1/directory/employees', params={'q': 'завуч'})).json()
        assert [p['id'] for p in found] == [observer.person_id]
        response = await client.patch(
            f'/api/v1/publishings/{built["publishing"]["id"]}', json={'observer_person_ids': [observer.person_id]}
        )
        assert [o['email'] for o in response.json()['observers']] == ['head@skolkovo.example.org']

        cabinet = (await observer_client.get('/api/v1/publishings')).json()
        assert [p['id'] for p in cabinet] == [built['publishing']['id']] and cabinet[0]['can_edit'] is False
        assert (await observer_client.get(f'/api/v1/surveys/{built["survey"]["id"]}')).status_code == 404
        assert (
            await observer_client.patch(f'/api/v1/publishings/{built["publishing"]["id"]}', json={'title': 'X'})
        ).status_code == 404

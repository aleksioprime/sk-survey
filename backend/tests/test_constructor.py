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
    assert survey['role'] == 'editor'
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
    creator = await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).json()
    url = f'/api/v1/surveys/{survey["id"]}'
    colleague = Person(last_name='Коллега', email='colleague@example.org', is_employee=True)
    db.add(colleague)
    await db.commit()

    assigned = await client.put(f'{url}/members', json={'editor_person_ids': [colleague.id]})
    assert assigned.status_code == 200, assigned.text
    assert {member['role'] for member in assigned.json()['members']} == {'editor'}
    assert {member['person_id'] for member in assigned.json()['members']} == {creator.person_id, colleague.id}


async def test_any_editor_can_manage_access_and_delete(db, client):
    creator = await login_employee(db, client)
    survey = (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).json()
    url = f'/api/v1/surveys/{survey["id"]}'
    async with other_client(client) as editor_client:
        editor = await login_employee(db, editor_client, email='editor@example.org')
        added = await client.put(
            f'{url}/access',
            json={
                'members': [{'user_id': creator.id}, {'person_id': editor.person_id}],
                'expected_user_ids': [creator.id],
            },
        )
        assert added.status_code == 200, added.text
        assert (await editor_client.patch(url, json={'title': 'Новое'})).status_code == 200
        assert (await editor_client.put(f'{url}/access', json={'members': []})).status_code == 400
        stale = await editor_client.put(
            f'{url}/access', json={'members': [{'user_id': editor.id}], 'expected_user_ids': [editor.id]}
        )
        assert stale.status_code == 409

        updated = await editor_client.put(
            f'{url}/access',
            json={'members': [{'user_id': editor.id}], 'expected_user_ids': [creator.id, editor.id]},
        )
        assert updated.status_code == 200, updated.text
        assert [member['user_id'] for member in updated.json()['members']] == [editor.id]
        assert (await client.get(url)).status_code == 404
        assert (await client.delete(url)).status_code == 404
        assert (await editor_client.delete(url)).status_code == 204


async def test_admin_can_manage_access_with_an_account_outside_the_directory(db, client):
    admin = await login_as(db, client, is_superuser=True)
    admin.person = None
    employee = Person(last_name='Сотрудник', email='employee@example.org', is_employee=True)
    db.add(employee)
    await db.commit()

    survey = (await client.post('/api/v1/surveys', json={'title': 'Опрос'})).json()
    url = f'/api/v1/surveys/{survey["id"]}'
    members = [{'user_id': admin.id}, {'person_id': employee.id}]
    shared = await client.put(f'{url}/access', json={'members': members})
    assert shared.status_code == 200, shared.text
    by_person = {member['person_id']: member for member in shared.json()['members']}
    assert set(by_person) == {None, employee.id}
    assert {member['role'] for member in by_person.values()} == {'editor'}

    changed = await client.put(f'{url}/access', json={'members': [{'user_id': by_person[employee.id]['user_id']}]})
    assert changed.status_code == 200, changed.text
    assert changed.json()['role'] == 'editor'
    assert (await client.get(url)).json()['role'] == 'editor'
    assert (await client.get('/api/v1/surveys')).json()[0]['role'] == 'editor'
    assert (await client.delete(url)).status_code == 204


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

    # Тип отвеченного вопроса менять нельзя, удалять - тоже
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
    survey_id = built['survey']['id']
    publication_id = built['publishing']['id']
    before = (await client.get('/api/v1/surveys')).json()
    assert before[0]['result_publication_id'] == publication_id
    other = await client.post(f'/api/v1/surveys/{survey_id}/publishings', json={'title': 'Другая публикация'})
    assert other.status_code == 201
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
        assert (await observer_client.get('/api/v1/surveys')).json() == []
        catalog = (await observer_client.get('/api/v1/surveys', params={'include_observed': True})).json()
        assert len(catalog) == 1
        assert catalog[0]['id'] == survey_id and catalog[0]['role'] == 'observer'
        assert catalog[0]['publishings_count'] == 1 and catalog[0]['result_publication_id'] == publication_id
        assert catalog[0]['questions_count'] == 0 and catalog[0]['code'] is None
        results = (await observer_client.get('/api/v1/publishings', params={'survey_id': survey_id})).json()
        assert [p['id'] for p in results] == [publication_id]
        assert (await observer_client.get(f'/api/v1/surveys/{survey_id}/publishings')).status_code == 404
        assert (await observer_client.get(f'/api/v1/surveys/{built["survey"]["id"]}')).status_code == 404
        assert (
            await observer_client.put(f'/api/v1/surveys/{survey_id}/access', json={'members': []})
        ).status_code == 404
        assert (await observer_client.delete(f'/api/v1/surveys/{survey_id}')).status_code == 404
        assert (
            await observer_client.patch(f'/api/v1/publishings/{built["publishing"]["id"]}', json={'title': 'X'})
        ).status_code == 404
        archived = await client.patch(f'/api/v1/surveys/{survey_id}', json={'is_active': False})
        assert archived.status_code == 200
        publications = (await observer_client.get('/api/v1/publishings', params={'survey_id': survey_id})).json()
        assert [(p['id'], p['survey_is_active']) for p in publications] == [(publication_id, False)]
        assert (await observer_client.get(f'/api/v1/publishings/{publication_id}/results')).status_code == 200
        public_path = f'/api/v1/public/s/{built["publishing"]["public_token"]}'
        assert (await observer_client.get(public_path)).status_code == 404
        restored = await client.patch(f'/api/v1/surveys/{survey_id}', json={'is_active': True})
        assert restored.status_code == 200
        assert (await observer_client.get(public_path)).status_code == 200
    own_catalog = (await client.get('/api/v1/surveys', params={'include_observed': True})).json()
    assert own_catalog[0]['publishings_count'] == 2 and own_catalog[0]['result_publication_id'] is None


async def test_scale_usage_is_limited_to_surveys_the_user_can_edit(db, client):
    await login_employee(db, client)
    built = await build_survey(client)
    survey = built['survey']
    scale_id = built['questions']['scale']['scale_id']
    scale_url = f'/api/v1/scales/{scale_id}'
    scales = (await client.get('/api/v1/scales', params={'include_usage': True})).json()
    assert next(scale for scale in scales if scale['id'] == scale_id)['used_in'] == [
        {'id': survey['id'], 'title': survey['title'], 'is_active': True}
    ]
    assert (await client.patch(f'/api/v1/surveys/{survey["id"]}', json={'is_active': False})).status_code == 200
    async with other_client(client) as stranger:
        await login_employee(db, stranger, email='other-scales@example.org', last_name='Другой')
        visible = (await stranger.get('/api/v1/scales', params={'include_usage': True})).json()
        scale = next(scale for scale in visible if scale['id'] == scale_id)
        assert scale['used_in'] == [] and scale['can_delete'] is False
        assert (await stranger.put(scale_url, json={'title': 'Новое название'})).status_code == 409
        assert (await stranger.delete(scale_url)).status_code == 409
    assert (await client.delete(scale_url)).status_code == 409
    saved = (await client.get(f'/api/v1/surveys/{survey["id"]}')).json()
    assert next(q for q in saved['questions'] if q['question_type'] == 'scale')['scale_id'] == scale_id


async def test_update_and_delete_unused_scale(db, client):
    await login_employee(db, client)
    data = {
        'title': 'Неиспользуемая шкала',
        'scale_type': 'items',
        'items': [{'title': 'Согласен', 'description': 'Описание', 'value': 'agree', 'score': 3}],
    }
    created = await client.post('/api/v1/scales', json=data)
    assert created.status_code == 201
    scale = created.json()
    assert scale['can_delete'] is True
    url = f'/api/v1/scales/{scale["id"]}'
    item = scale['items'][0]
    edited = await client.put(url, json={**data, 'title': 'Новая шкала', 'items': [{**item, 'title': 'Да'}]})
    assert edited.status_code == 200
    updated = edited.json()
    assert updated['id'] == scale['id'] and updated['title'] == 'Новая шкала' and updated['can_delete'] is True
    assert updated['items'] == [{**item, 'title': 'Да'}]
    async with other_client(client) as student:
        await login_as(db, student, email='student@example.org')
        assert (await student.put(url, json=data)).status_code == 403
        assert (await student.delete(url)).status_code == 403
    assert (await client.delete(url)).status_code == 204
    assert (await client.delete(url)).status_code == 404
    assert all(row['id'] != scale['id'] for row in (await client.get('/api/v1/scales')).json())

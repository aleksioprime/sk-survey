from sk_common.testing import login_as


async def login_employee(db, client, email='psy@skolkovo.example.org', last_name='Психологова'):
    user = await login_as(db, client, email=email, last_name=last_name)
    user.person.is_employee = True
    await db.commit()
    return user


SCALE = {'title': 'Шкала 1–10', 'scale_type': 'generated', 'min_value': 1, 'max_value': 10, 'step': 1}


async def build_survey(client, anonymous=True) -> dict:
    """Опрос со всеми типами вопросов и публикация. Возвращает опрос, вопросы по типу и публикацию."""
    scale = (await client.post('/api/v1/scales', json=SCALE)).json()
    survey = (await client.post('/api/v1/surveys', json={'title': 'Пульс-опрос', 'thank_you_text': 'Спасибо!'})).json()
    sid = survey['id']
    section = (await client.post(f'/api/v1/surveys/{sid}/sections', json={'title': 'Работа'})).json()
    options = [{'title': 'Да, полностью'}, {'title': 'Частично'}, {'title': 'Нет'}]
    specs = {
        'text': {'is_required': True},
        'rich_text': {},
        'single_choice': {'options': options, 'is_required': True},
        'multiple_choice': {'options': options, 'min_selections': 1, 'max_selections': 2},
        'number': {'min_number': 0, 'max_number': 100},
        'yes_no': {},
        'scale': {
            'scale_id': scale['id'],
            'ranges': [
                {'title': 'Низкая', 'from_value': 1, 'to_value': 3},
                {'title': 'Средняя', 'from_value': 4, 'to_value': 7},
                {'title': 'Высокая', 'from_value': 8, 'to_value': 10},
            ],
        },
        'ranking': {'options': options},
    }
    questions = {}
    for kind, extra in specs.items():
        response = await client.post(
            f'/api/v1/surveys/{sid}/questions',
            json={'text': f'Вопрос {kind}', 'question_type': kind, 'section_id': section['id'], **extra},
        )
        assert response.status_code == 201, response.text
        questions[kind] = response.json()
    publishing = (
        await client.post(f'/api/v1/surveys/{sid}/publishings', json={'title': 'Весна', 'is_anonymous': anonymous})
    ).json()
    return {'survey': survey, 'section': section, 'questions': questions, 'publishing': publishing, 'scale': scale}


def full_answers(questions: dict) -> dict[str, dict]:
    opts = {kind: [o['id'] for o in q['options']] for kind, q in questions.items()}
    return {
        'text': {'text_value': 'Всё хорошо'},
        'rich_text': {'rich_text_value': '<p>Ок <script>alert(1)</script><b>жирный</b></p>'},
        'single_choice': {'option_id': opts['single_choice'][0]},
        'multiple_choice': {'option_ids': opts['multiple_choice'][:2]},
        'number': {'number_value': 42},
        'yes_no': {'boolean_value': True},
        'scale': {'number_value': 8},
        'ranking': {'ranking': list(reversed(opts['ranking']))},
    }

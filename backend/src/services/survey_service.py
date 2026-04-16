"""
Сервис для работы с публичными опросами.

Содержит всю бизнес-логику прохождения опроса: загрузка бандла с метаданными,
создание анонимных ответов, сохранение ответов на вопросы и финализация.
Взаимодействует с NocoBase через HTTP-клиент.
"""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from src.core.nocobase import nocobase
from src.schemas import AnswerPayload

logger = logging.getLogger('sk_survey')


class SurveyService:
    """Бизнес-логика публичного прохождения опросов."""

    async def _get_publishing(self, token: str) -> dict:
        """Найти активную публикацию по токену."""
        result = await nocobase.get(
            'survey_publishings',
            filter={'public_token': token, 'is_active': True},
            appends='survey',
        )
        if not result:
            raise HTTPException(status_code=404, detail='Опрос не найден или не активен')
        return result

    async def get_bundle(self, token: str, response_token: str | None = None) -> dict:
        """Собрать полный бандл опроса: метаданные, разделы, вопросы, варианты, шкалы.
        Если передан response_token — подгрузить существующие ответы для возобновления."""
        publishing = await self._get_publishing(token)
        survey_id = publishing.get('survey_id') or publishing.get('survey', {}).get('id')

        survey = await nocobase.get_by_id('surveys', survey_id)

        sections = await nocobase.list(
            'survey_sections',
            filter={'survey_id': survey_id, 'is_active': True},
            sort='order',
        )

        questions = await nocobase.list(
            'survey_questions',
            filter={'survey_id': survey_id, 'is_active': True},
            sort='order',
            appends='scale',
        )

        question_ids = [q['id'] for q in questions]

        options = []
        if question_ids:
            options = await nocobase.list(
                'survey_question_options',
                filter={'question_id.$in': question_ids, 'is_active': True},
                sort='order',
            )

        scale_ids = list({q['scale_id'] for q in questions if q.get('scale_id')})
        scale_items = []
        if scale_ids:
            scale_items = await nocobase.list(
                'survey_scale_items',
                filter={'scale_id.$in': scale_ids},
                sort='order',
                pageSize=1000,
            )

        scale_ranges = []
        if question_ids:
            scale_ranges = await nocobase.list(
                'survey_question_scale_ranges',
                filter={'question_id.$in': question_ids},
                sort='order',
                pageSize=1000,
            )

        # Попытка восстановить существующую сессию
        existing_response = None
        existing_answers = []
        if response_token:
            existing_response = await nocobase.get(
                'survey_responses',
                filter={'token': response_token, 'status': 'in_progress'},
            )
            if existing_response:
                existing_answers = await nocobase.list(
                    'survey_answers',
                    filter={'response_id': existing_response['id']},
                    appends='options',
                )
                existing_answers = await self._append_ranking_items(existing_answers)

        return {
            'publishing': publishing,
            'survey': survey,
            'sections': sections if isinstance(sections, list) else [],
            'questions': questions if isinstance(questions, list) else [],
            'options': options if isinstance(options, list) else [],
            'scale_items': scale_items if isinstance(scale_items, list) else [],
            'scale_ranges': scale_ranges if isinstance(scale_ranges, list) else [],
            'existing_response': existing_response,
            'existing_answers': existing_answers if isinstance(existing_answers, list) else [],
        }

    async def _append_ranking_items(self, answers: list[dict]) -> list[dict]:
        """Подмешать ranking-items к существующим ответам при восстановлении сессии."""
        if not answers:
            return answers

        answer_ids = [a.get('id') for a in answers if a.get('id')]
        if not answer_ids:
            return answers

        ranking_rows = await nocobase.list(
            'survey_answer_ranking_items',
            filter={'answer_id.$in': answer_ids},
            sort='rank',
            pageSize=1000,
        )

        by_answer: dict[int, list[dict]] = {}
        for row in ranking_rows if isinstance(ranking_rows, list) else []:
            answer_id = row.get('answer_id')
            if not answer_id:
                continue
            by_answer.setdefault(answer_id, []).append(row)

        for answer in answers:
            answer['ranking_items'] = by_answer.get(answer.get('id'), [])

        return answers

    async def _validate_ranking_payload(
        self,
        question: dict,
        ranking_option_ids: list[int],
    ):
        """Проверить корректность ranking-ответа для конкретного вопроса."""
        if question.get('question_type') != 'ranking':
            raise HTTPException(status_code=400, detail='ranking_option_ids допустим только для ranking-вопросов')

        if len(ranking_option_ids) != len(set(ranking_option_ids)):
            raise HTTPException(status_code=400, detail='ranking_option_ids содержит дубли')

        selected_count = len(ranking_option_ids)
        min_selections = question.get('min_selections')
        max_selections = question.get('max_selections')

        if min_selections and selected_count < min_selections:
            raise HTTPException(status_code=400, detail='Выбрано меньше вариантов, чем min_selections')

        if max_selections and selected_count > max_selections:
            raise HTTPException(status_code=400, detail='Выбрано больше вариантов, чем max_selections')

        if not ranking_option_ids:
            return

        question_id = question['id']
        available_options = await nocobase.list(
            'survey_question_options',
            filter={'question_id': question_id, 'is_active': True},
            pageSize=1000,
        )
        allowed_ids = {opt.get('id') for opt in available_options if opt.get('id')}

        invalid = [oid for oid in ranking_option_ids if oid not in allowed_ids]
        if invalid:
            raise HTTPException(status_code=400, detail='ranking_option_ids содержит варианты не из текущего вопроса')

    async def start_response(self, token: str) -> dict:
        """Создать новый response для данной публикации."""
        publishing = await self._get_publishing(token)
        publishing_id = publishing['id']

        anon_token = secrets.token_urlsafe(32)

        response = await nocobase.create('survey_responses', {
            'publishing': publishing_id,
            'status': 'in_progress',
            'token': anon_token,
        })

        return response

    async def save_answer(
        self,
        token: str,
        response_id: int,
        question_id: int,
        payload: AnswerPayload,
    ) -> dict:
        """Сохранить или обновить ответ на вопрос."""
        await self._get_publishing(token)

        existing = await nocobase.get(
            'survey_answers',
            filter={'response_id': response_id, 'question_id': question_id},
        )

        question = await nocobase.get_by_id('survey_questions', question_id)
        if not question:
            raise HTTPException(status_code=404, detail='Вопрос не найден')

        answer_data = payload.model_dump(exclude_none=True)
        option_ids = answer_data.pop('option_ids', None)
        ranking_option_ids = answer_data.pop('ranking_option_ids', None)

        if ranking_option_ids is not None:
            await self._validate_ranking_payload(question, ranking_option_ids)

        if existing:
            result = await nocobase.update('survey_answers', existing['id'], answer_data)
            if option_ids is not None:
                await self._set_answer_options(existing['id'], option_ids)
            if ranking_option_ids is not None:
                await self._set_answer_ranking_items(existing['id'], ranking_option_ids)
            return result
        else:
            # NocoBase требует имена ассоциаций (response, question) при создании,
            # а не FK-колонки (response_id, question_id)
            answer_data['response'] = response_id
            answer_data['question'] = question_id
            result = await nocobase.create('survey_answers', answer_data)
            if option_ids is not None:
                await self._set_answer_options(result['id'], option_ids)
            if ranking_option_ids is not None:
                await self._set_answer_ranking_items(result['id'], ranking_option_ids)
            return result

    async def _set_answer_options(self, answer_id: int, option_ids: list[int]):
        """Установить ManyToMany связь ответа с вариантами (для множественного выбора)."""
        await nocobase.update('survey_answers', answer_id, {
            'options': [{'id': oid} for oid in option_ids],
        })

    async def _set_answer_ranking_items(self, answer_id: int, option_ids: list[int]):
        """Перезаписать ranking-элементы ответа в заданном порядке."""
        existing_rows = await nocobase.list(
            'survey_answer_ranking_items',
            filter={'answer_id': answer_id},
            pageSize=1000,
        )

        for row in existing_rows if isinstance(existing_rows, list) else []:
            row_id = row.get('id')
            if row_id:
                await nocobase.delete('survey_answer_ranking_items', row_id)

        for rank, option_id in enumerate(option_ids, start=1):
            await nocobase.create('survey_answer_ranking_items', {
                'answer': answer_id,
                'option': option_id,
                'rank': rank,
            })

    async def submit_response(self, token: str, response_id: int) -> dict:
        """Финализировать ответ."""
        await self._get_publishing(token)

        result = await nocobase.update('survey_responses', response_id, {
            'status': 'submitted',
            'submitted_at': datetime.now(timezone.utc).isoformat(),
        })
        return result


survey_service = SurveyService()

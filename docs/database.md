**Опросы (surveys):**
Название (title)
Код (code)
Описание (description)
Вступительный текст (intro_text)
Текст после отправки (thank_you_text)
Активный (is_active)

**Публикации опросов (survey_publishings):**
Опрос (survey_id)
Название (title)
Публичный токен (public_token)
Активна (is_active)
Анонимный опрос (is_anonymous)

**Разделы опросов (survey_sections):**
Опрос (survey_id)
Название (title)
Описание (description)
Порядок (order)
Активный (is_active)

**Шкалы опросов (survey_scales):**
Название (title)
Описание (description)
Тип шкалы (scale_type)
- generated — Генерируемая
- items — По элементам
Минимальное значение (min_value)
Максимальное значение (max_value)
Шаг (step)

**Элементы шкалы опросов (survey_scale_items):**
Шкала (scale_id)
Название (title)
Пояснение (description)
Значение (value)
Баллы (score)
Порядок (order)

**Вопросы опросов (survey_questions):**
Опрос (survey_id)
Раздел (section_id)
Текст вопроса (text)
Пояснение (description)
Тип вопроса (question_type)
- text — Текст
- rich_text — Форматированный текст
- single_choice — Одиночный выбор
- multiple_choice — Множественный выбор
- number — Число
- yes_no — Да/Нет
- scale — Шкала
- ranking - Расставить по порядку
Порядок (order)
Обязательный (is_required)
Активный (is_active)
Шкала (scale_id)
Минимум выборов (min_selections)
Максимум выборов (max_selections)
Минимальное число (min_number)
Максимальное число (max_number)
Случайный порядок вариантов (is_options_shuffled)

**Варианты ответов (survey_question_options):**
Вопрос (question_id)
Текст варианта (title)
Пояснение (description)
Значение (value)
Баллы (score)
Порядок (order)
Активный (is_active)

**Ответы на опросы (survey_responses):**
Публикация опроса (publishing_id)
Пользователь (user_id)
Анонимный токен (token)
Статус (status — выбор):
- in_progress — В процессе
- submitted — Отправлен
Дата отправки (submitted_at)

**Ответы на вопросы (survey_answers):**
Ответ на опрос (response_id)
Вопрос (question_id)
Текстовый ответ (text_value)
Форматированный ответ (rich_text_value)
Числовой ответ (number_value)
Ответ да/нет (boolean_value)
Элемент шкалы (scale_item_id)
Выбранный вариант (option_id)
Пропущен (is_skipped)
Выбранные варианты (options - ManyToMany)

**Ответы выбора порядка (survey_answer_ranking_items)**
Ответ (answer_id)
Вариант (option_id)
Позиция (rank)

**Диапазоны шкалы вопроса (survey_question_scale_ranges):**
Вопрос (question_id)
Название диапазона (title)
От значения (from_value)
До значения (to_value)
Порядок (order)
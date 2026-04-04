# SK Survey

Платформа для анонимного прохождения психологических опросов для Гимназии Сколково.

Опросы создаются и управляются в [NocoBase](https://flow.skeducator.ru). Данное приложение — публичный интерфейс для прохождения, хранения и отправки ответов.

---

## Архитектура

```
[Браузер]
    │  /backend/*
    ▼
[Frontend — Vue 3 SPA]  ← dev: Vite proxy  ← prod: nginx proxy
    │  /api/v1/*
    ▼
[Backend — FastAPI BFF]
    │  HTTPS REST API
    ▼
[NocoBase — Headless CMS]  (cloud, flow.skeducator.ru)
```

**BFF (Backend for Frontend)** — промежуточный сервер, который:
- скрывает API-ключ NocoBase от браузера
- агрегирует данные (survey bundle — всё в одном запросе)
- управляет жизненным циклом анонимных ответов

Авторизации нет — все опросы анонимны. Доступ по `public_token` из публикации.

---

## Стек технологий

| Слой      | Технология                                  |
|-----------|---------------------------------------------|
| Backend   | Python 3.12, FastAPI 0.115, httpx, Pydantic |
| Frontend  | Vue 3.5, Vite 8, Pinia, Vue Router, Axios   |
| Стили     | Tailwind CSS v4                             |
| CMS       | NocoBase (внешний сервис)                   |
| Контейнеры| Docker, docker-compose                      |
| CI/CD     | GitHub Actions → GHCR → Coolify            |

---

## Быстрый старт (локально, Docker)

### 1. Клонировать репозиторий

```bash
git clone https://github.com/aleksioprime/sk-survey.git
cd sk-survey
```

### 2. Создать `.env` файл

```bash
cp .env.example .env
```

Заполнить:

```env
# NocoBase API-ключ (обязательно)
API_KEY=eyJ...

# URL NocoBase
NOCOBASE_URL=https://flow.skeducator.ru

# Разрешённые origins CORS
CORS_ALLOW_ORIGINS=http://localhost:3000

# Порты (опционально)
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

### 3. Запустить

```bash
docker compose -p sk-survey up -d --build
```

Приложение будет доступно по адресу `http://localhost:3000`.

Опрос открывается по URL вида: `http://localhost:3000/s/<public_token>`

---

## Запуск без Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export API_KEY=eyJ...
export NOCOBASE_URL=https://flow.skeducator.ru
export CORS_ALLOW_ORIGINS=http://localhost:5173

uvicorn src.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend/app
npm install

# В .env.local:
# VITE_BACKEND_API_PROXY_URL=http://localhost:8000/api/v1

npm run dev
```

---

## Переменные окружения

### Backend (`.env`)

| Переменная          | Описание                           | Значение по умолчанию          |
|---------------------|------------------------------------|-------------------------------|
| `API_KEY`           | API-ключ NocoBase (обязательно)    | —                             |
| `NOCOBASE_URL`      | URL NocoBase                       | `https://flow.skeducator.ru`  |
| `NOCOBASE_TIMEOUT`  | Таймаут HTTP-запросов (сек)        | `30`                          |
| `CORS_ALLOW_ORIGINS`| Разрешённые CORS-origins (запятая) | —                             |
| `HOST`              | Адрес прослушивания                | `0.0.0.0`                     |
| `PORT`              | Порт сервера                       | `8000`                        |

### Frontend (`.env` / build args)

| Переменная                  | Описание                         | Значение по умолчанию     |
|-----------------------------|----------------------------------|---------------------------|
| `VITE_BACKEND_API_URL`      | Базовый URL BFF в браузере       | `/backend`                |
| `VITE_BACKEND_API_PROXY_URL`| URL для Vite-прокси (dev/Docker) | `http://localhost:8000/api/v1` |
| `VITE_LOGGING`              | Включить debug-логи (0/1)        | `0`                       |

---

## Структура проекта

```
sk-survey/
├── backend/
│   ├── src/
│   │   ├── core/
│   │   │   ├── config.py         # Настройки из env-переменных
│   │   │   ├── logging.py        # Middleware логирования запросов
│   │   │   └── nocobase.py       # HTTP-клиент к NocoBase REST API
│   │   ├── routes/
│   │   │   └── v1/
│   │   │       └── public/
│   │   │           └── surveys.py  # Публичные эндпоинты опросов
│   │   ├── schemas/
│   │   │   └── __init__.py       # Pydantic-схемы (AnswerPayload)
│   │   ├── services/
│   │   │   └── survey_service.py # Бизнес-логика
│   │   └── main.py               # FastAPI-приложение
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   └── src/
│   │       ├── api/
│   │       │   └── public.js     # Axios-клиент к BFF
│   │       ├── components/
│   │       │   ├── ProgressBar.vue
│   │       │   ├── QuestionCard.vue           # Диспетчер типов вопросов
│   │       │   └── questions/
│   │       │       ├── TextQuestion.vue
│   │       │       ├── RichTextQuestion.vue
│   │       │       ├── SingleChoiceQuestion.vue
│   │       │       ├── MultipleChoiceQuestion.vue
│   │       │       ├── NumberQuestion.vue
│   │       │       ├── YesNoQuestion.vue
│   │       │       └── ScaleQuestion.vue
│   │       ├── router/
│   │       │   └── index.js      # Vue Router маршруты
│   │       ├── stores/
│   │       │   └── survey.js     # Pinia: состояние + логика опроса
│   │       ├── views/
│   │       │   ├── SurveyView.vue           # Основная страница опроса
│   │       │   ├── SurveyCompleteView.vue   # Страница благодарности
│   │       │   └── NotFoundView.vue         # 404
│   │       ├── App.vue
│   │       ├── main.js
│   │       └── style.css
│   ├── nginx/
│   │   └── nginx.conf            # Prod nginx: SPA + proxy → backend
│   └── Dockerfile
├── .github/
│   └── workflows/
│       ├── build.yml             # Сборка и push в GHCR
│       └── deploy.yml            # Деплой через Coolify API
├── docker-compose.yaml           # Dev-окружение
├── docker-compose.prod.yaml      # Production
├── .env.example
└── docs/
    └── database.md               # Схема данных NocoBase
```

---

## API

**Base URL:** `/api/v1`

| Метод   | Путь                                                     | Описание                           |
|---------|----------------------------------------------------------|------------------------------------|
| `GET`   | `/public/surveys/{token}`                                | Получить бандл опроса              |
| `POST`  | `/public/surveys/{token}/start`                          | Начать прохождение                 |
| `PATCH` | `/public/surveys/{token}/responses/{id}/answers/{qid}`   | Сохранить/обновить ответ           |
| `POST`  | `/public/surveys/{token}/responses/{id}/submit`          | Отправить завершённый ответ        |
| `GET`   | `/health`                                                | Health check                       |

Документация (Swagger): `http://localhost:8000/api/openapi`

---

## Прохождение опроса

1. Переходим по `/s/<public_token>`
2. Читаем вступительный текст, нажимаем **Начать опрос**
3. Заполняем вопросы раздела:
   - Выборы (радио/чекбоксы/шкала/да-нет) **сохраняются автоматически**
   - Текстовые ответы — по кнопке **Сохранить ответ**
   - Сохранённые вопросы выделяются зелёным
4. Навигация по разделам: **← Назад** / **Далее →**
5. На последнем разделе — кнопка **Отправить ответы**

### Возобновление сессии

Если закрыть вкладку и снова перейти по той же ссылке — сессия восстановится автоматически.
Данные хранятся в `localStorage` под ключом `sk_survey_<token>`.
После успешной отправки данные из localStorage очищаются.

---

## CI/CD

### `build.yml`

Запускается при push в `main` (изменения в `frontend/`, `backend/` или workflow-файлах).

1. **test** — сборка frontend (Node 20) + компиляция backend (Python 3.12)
2. **build** — сборка Docker-образов и push в GHCR:
   - `ghcr.io/aleksioprime/sk-survey-frontend:<sha> и :latest`
   - `ghcr.io/aleksioprime/sk-survey-backend:<sha> и :latest`

### `deploy.yml`

Запускается автоматически после успешного `build.yml` (через `workflow_run`) или вручную.

1. Определяет тег образа (SHA из workflow_run или `latest`)
2. Обновляет `FRONTEND_IMAGE_TAG` и `BACKEND_IMAGE_TAG` в Coolify через API
3. Запускает деплой приложения

**Secrets в GitHub:**

| Secret           | Описание                         |
|------------------|----------------------------------|
| `COOLIFY_API`    | URL Coolify API                  |
| `COOLIFY_TOKEN`  | Bearer-токен Coolify             |
| `COOLIFY_APP`    | UUID приложения в Coolify        |

---

## Схема данных

Полная схема коллекций NocoBase: [docs/database.md](docs/database.md)
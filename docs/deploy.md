# Развёртывание в Coolify

Прод — ресурс «Docker Compose» в проекте Survey панели `devops.skolhub.ru` (сервер `skl-web-app`)
с файлом [`infra/coolify/docker-compose.prod.yaml`](../infra/coolify/docker-compose.prod.yaml).
Образы собирает GitHub Actions при пуше в `main`; API идёт через nginx фронтенда, нужен один домен.

## 1. DNS

`survey.skolhub.ru` — A-запись на `5.252.65.50` (вся зона `skolhub.ru` уже ведёт туда).

## 2. Переменные

`.env.prod` в корне репозитория (в git не попадает):

```
COOLIFY_URL=https://devops.skolhub.ru
COOLIFY_API_TOKEN=…
SECRET_KEY=…              # openssl rand -hex 32
DB__PASSWORD=…            # openssl rand -hex 16
BOOTSTRAP_ADMIN_EMAILS=["…"]
SMTP__USER=…
SMTP__PASSWORD=…
SKOLSTREAM__CLIENT_ID=…
SKOLSTREAM__CLIENT_SECRET=…
SKOLSTREAM__DIRECTORY_TOKEN=…
```

## 3. Ресурс

```bash
python3 infra/coolify/deploy.py --dry-run
python3 infra/coolify/deploy.py
```

Скрипт создаёт ресурс `sk-survey`, передаёт переменные, задаёт домен и запускает сборку. Домены Coolify
принимает после первой сборки — тогда скрипт нужно запустить ещё раз.

Дальше выкатка автоматическая: после пуша в `main` workflow «Образы» собирает образы, записывает тег коммита
в переменную `IMAGE_TAG` ресурса и запускает развёртывание. Секреты репозитория: `COOLIFY_API`
(`https://devops.skolhub.ru/api/v1`), `COOLIFY_APP` (UUID ресурса), `COOLIFY_TOKEN` (токен панели с правами
write и deploy). Откат — `git revert` в `main` или в панели `IMAGE_TAG` = SHA прежнего коммита и Redeploy.

## 4. Перенос из NocoBase

Разовая операция. Выгрузка только читает API NocoBase (ключ — на время выгрузки):

```bash
NOCOBASE_URL=https://flow.skolhub.ru NOCOBASE_API_KEY=… python -m app.cli nocobase-fetch ./nocobase
```

JSON-файлы копируются в том `nocobase_data` контейнера `backend`, затем:

```bash
python -m app.cli nocobase-load /data/nocobase <email владельца опросов>
```

- ID записей и токены публикаций сохраняются — старые ссылки `/s/<токен>` работают на новом домене;
- начатые прохождения переносятся с хешем ключа: человек может дописать опрос;
- наблюдатели публикаций сопоставляются с людьми из SkolStream по UUID, затем по email;
- владелец (второй аргумент) получает все перенесённые опросы в конструкторе;
- повторный запуск пропускает уже перенесённое; `report.json` — что пропущено и почему.

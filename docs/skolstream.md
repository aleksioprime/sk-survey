# SkolStream: вход и справочник

Общая часть - пакет [sk-common](https://github.com/aleksioprime/sk-common): там описаны правила
справочника и подключение. Здесь - что нужно именно SK Survey.

## Вход

OAuth-приложение «SK Survey» в админке SkolStream (Django OAuth Toolkit → Applications):

- Client type - Confidential, Authorization grant type - Authorization code;
- Redirect uris - `https://survey.skolhub.ru/api/v1/auth/skolstream/callback`;
- Skip authorization - включить;
- client secret скопировать до сохранения → `SKOLSTREAM__CLIENT_SECRET`.

Вход через SkolStream нужен авторам и наблюдателям (кабинет) и отвечающим на неанонимные публикации.
Анонимные опросы проходят без входа.

## Справочник

Токен выгрузки справочника в админке SkolStream («Токены выгрузки справочника», отдельный на сервис) →
`SKOLSTREAM__DIRECTORY_TOKEN`. Изменения подтягиваются каждые 10 минут, полный срез - ночью,
вручную - «Люди» → «Обновить из SkolStream».

Из справочника берутся сотрудники (кто может создавать опросы, поиск редакторов и наблюдателей) и
ученики с классами (ФИО и класс в выгрузке неанонимных публикаций).

## Сеть

В проде backend и worker ходят на публичный адрес SkolStream (`extra_hosts`, `SKOLSTREAM__PUBLIC_IP`):
внутренний DNS гимназии отдаёт адрес ingress, недоступный из DMZ.

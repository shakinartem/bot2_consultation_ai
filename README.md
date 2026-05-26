# БОТ 2 — SHARiK digital Consultation AI

БОТ 2 помогает менеджеру ШАРиК digital проводить консультации со стоматологическими клиниками после холодного звонка из БОТА 1 CRM.

Связка MVP:

- БОТ 1 переводит подходящие компании в `consultation_planned`.
- БОТ 2 получает компании через `CRM_ADAPTER`.
- БОТ 2 подтягивает consultation context из БОТА 1, если endpoint доступен.
- БОТ 2 генерирует AI-аудит, предварительное предложение и DOCX для менеджера и клиента.
- БОТ 2 отправляет итог консультации обратно в БОТ 1 через handoff API.

## Возможности MVP

- Telegram-first сценарий для менеджера.
- Список клиентов на консультацию из CRM.
- Карточка клиники с заметками, ссылками и материалами.
- AI-аудит с учетом контекста продаж.
- Предварительное предложение с безопасным fallback без внешнего AI.
- DOCX "AI-аудит и предварительное предложение".
- API endpoints для будущего web/mini app.
- Mock CRM для локального запуска без БОТА 1.

## Установка

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Заполните `.env`.

```env
BOT_TOKEN=telegram_bot_token
DATABASE_URL=sqlite+aiosqlite:///./app.db

API_TOKEN=
API_AUTH_ENABLED=false

AI_PROVIDER=fallback

CRM_ADAPTER=mock
CRM_API_BASE_URL=http://localhost:8000
CRM_API_TOKEN=
CRM_READY_STATUSES=consultation_planned,consultation_scheduled
CRM_SHARED_DATABASE_URL=sqlite+aiosqlite:///../bot1_crm/app.db

PDF_EXPORT_ENABLED=false
PDF_EXPORT_PROVIDER=none

STORAGE_PATH=./storage
ADMIN_IDS=111,222,333

AGENCY_NAME=ШАРиК digital
AGENCY_PHONE=
AGENCY_TELEGRAM=
AGENCY_EMAIL=
AGENCY_WEBSITE=
AGENCY_CITY=
AGENCY_GEO=
AGENCY_LOGO_PATH=assets/brand/logo.png
```

## Manager Access

БОТ сейчас рассчитан на владельца и небольшой круг менеджеров.

- `ADMIN_IDS=111,222,333` — доступ только указанным Telegram ID.
- пустой `ADMIN_IDS` — dev mode, доступ не ограничен.
- сложного RBAC пока нет, это следующий этап.

Все Telegram handlers проверяют доступ через helper `is_admin()`.

## Запуск

```powershell
uvicorn app.main:app --reload
```

FastAPI поднимает:

- `/health`
- `/api/*`
- Telegram polling, если задан `BOT_TOKEN`

Для миграций:

```powershell
alembic upgrade head
```

Если `BOT_TOKEN` пустой, FastAPI и API стартуют без Telegram polling. Это удобно для smoke и локальных API-проверок.

## Telegram сценарий

Главное меню:

- `📋 Клиенты на консультацию`
- `🔎 Открыть карточку`
- `🧠 Сгенерировать аудит`
- `📄 Сгенерировать документ`
- `✅ Указать результат консультации`
- `🗂 Архив консультаций`
- `⚙️ Настройки AI`
- `❓ Помощь`

В карточке консультации доступны действия:

- `📝 Добавить заметку`
- `🔗 Добавить ссылки`
- `📎 Добавить материалы`
- `🧠 Сгенерировать аудит`
- `💼 Сформировать предложение`
- `📄 Сгенерировать DOCX`
- `✅ Итог консультации`

Команды:

- `/audit ID`
- `/proposal ID`
- `/docx ID`
- `/result ID`

## CRM_ADAPTER

Поддерживаются режимы:

- `mock` / `in_memory` — локальный тестовый режим.
- `http_api` — основной режим интеграции с БОТОМ 1.
- `sqlite_shared` — упрощенный режим чтения из общей SQLite базы.

Интерфейс adapter:

- `list_consultation_scheduled()`
- `get_company(company_id)`
- `get_consultation_context(company_id)`
- `update_company_status(company_id, status)`
- `add_interaction(company_id, type, result, notes)`
- `create_task(company_id, title, due_at, notes)`
- `send_consultation_result(company_id, result, notes)`

Если `http_api` не может получить consultation context по новому endpoint, БОТ 2 автоматически делает fallback на `get_company()` и собирает минимальный context локально.

## Интеграция с БОТОМ 1

Основной режим:

```env
CRM_ADAPTER=http_api
CRM_API_BASE_URL=http://localhost:8000
CRM_API_TOKEN=
CRM_READY_STATUSES=consultation_planned,consultation_scheduled
```

Если в БОТЕ 1 заполнен `BOT2_API_TOKEN`, то `CRM_API_TOKEN` в БОТЕ 2 должен совпадать с ним.

БОТ 2 использует:

- `GET /api/bot2/consultation-ready`
- `GET /api/bot2/companies/{company_id}/consultation-context`
- `POST /api/bot2/companies/{company_id}/consultation-result`

`GET /api/bot2/companies/{company_id}/consultation-context` возвращает расширенный sales context:

- данные компании
- ЛПР
- контакты
- историю касаний
- открытые задачи
- последний proposal
- последний call result
- `recommended_next_step`
- `sales_summary`

Если endpoint временно недоступен, БОТ 2 не падает и продолжает работать в fallback-режиме с минимальным context.

## AI Audit и Proposal

AI-аудит теперь учитывает:

- данные компании
- ЛПР и контакты
- историю касаний из CRM
- последний звонок и последний proposal
- открытые задачи
- `sales_summary`
- `recommended_next_step`
- заметки менеджера
- ссылки и материалы из консультации

Аудит сохраняет отдельные разделы:

- `# Контекст продаж`
- `# Что важно проговорить на консультации`

Предложение строится по структуре:

- `# Краткий вывод`
- `# Главная проблема клиента`
- `# Предлагаемое решение`
- `# Рекомендуемый пакет`
- `# Что входит`
- `# План внедрения`
- `# Бюджетный ориентир`
- `# Что нужно уточнить перед финальным КП`
- `# Следующий шаг`

Если внешний AI недоступен, deterministic fallback все равно генерирует audit и proposal.

Прайс в предложении использует текущие ориентиры ШАРиК digital и всегда формулируется как предварительный ориентир, без гарантированного результата и без выдуманных кейсов.

## DOCX и бренд

DOCX создается по пути:

```text
storage/docs/consultation_company_{company_id}_{consultation_id}.docx
```

Документ включает:

1. Обложку
2. Данные клиента
3. Контекст продаж
4. Главный вывод
5. Где клиника теряет заявки
6. Аудит сайта
7. Аудит карт
8. Аудит соцсетей
9. Репутацию
10. Основные проблемы
11. Точки роста
12. Roadmap 7/30/90 дней
13. Предварительное предложение
14. Следующий шаг
15. Подвал с контактами ШАРиК digital

Контакты агентства выводятся только если заполнены:

- телефон
- Telegram
- сайт
- email
- город
- география

Логотип опциональный. Если `assets/brand/logo.png` отсутствует, DOCX все равно генерируется.

## Брендовые ассеты

Папка:

```text
assets/brand/
```

Содержит:

- `.gitkeep`
- `README.md`

Туда можно положить `logo.png`. Рекомендуемый формат: PNG с прозрачным фоном.

## DOCX/PDF

PDF по-прежнему опционален:

```env
PDF_EXPORT_ENABLED=false
PDF_EXPORT_PROVIDER=none
```

Для локального PDF через LibreOffice:

```env
PDF_EXPORT_ENABLED=true
PDF_EXPORT_PROVIDER=libreoffice
```

Если LibreOffice недоступен, БОТ 2 отправляет DOCX и пишет понятное сообщение, что PDF не был собран.

## API endpoints

- `GET /health`
- `GET /api/consultations`
- `GET /api/consultations/{consultation_id}`
- `POST /api/consultations`
- `POST /api/consultations/{consultation_id}/notes`
- `POST /api/consultations/{consultation_id}/attachments/link`
- `POST /api/consultations/{consultation_id}/attachments/text`
- `POST /api/consultations/{consultation_id}/generate-audit`
- `POST /api/consultations/{consultation_id}/generate-proposal`
- `POST /api/consultations/{consultation_id}/generate-docx`
- `POST /api/consultations/{consultation_id}/result`
- `GET /api/crm/consultation-scheduled`
- `GET /api/crm/companies/{company_id}`

## Хранение файлов

```text
storage/
├── consultations/
├── docs/
└── clients/
```

Материалы клиента сохраняются в:

```text
storage/clients/company_{id}/
```

`.gitignore` должен исключать `.env`, SQLite базы и реальные клиентские файлы из `storage`.

## Smoke test

```powershell
py scripts/smoke_test.py
```

Проверяет:

- `/health`
- API auth на `/api/consultations`
- mock CRM
- `get_consultation_context()`
- fallback audit
- парсинг `sales_context` и `consultation_talking_points`
- fallback proposal
- API endpoint `POST /api/consultations/{id}/generate-proposal`
- DOCX генерацию
- сохранение результата консультации

## Docker Future / Local Compose Notes

Dev-файлы:

- `Dockerfile.dev`
- `.dockerignore`
- `docker/docker-compose.dev.yml`

Локальный compose поднимает только:

- `bot1-crm`
- `bot2-consultation`

Будущие сервисы `bot3-content`, `bot4-autoposter`, `bot5-reporter` уже добавлены как commented placeholders.

По умолчанию `docker/docker-compose.dev.yml` ожидает, что репозиторий БОТА 1 лежит по пути `../../bot1_crm`.
Если локальная папка называется иначе, замените `context` и `env_file` для сервиса `bot1-crm` вручную.

Запуск:

```powershell
docker compose -f docker/docker-compose.dev.yml up --build
```

Где лежат `.env`:

- для `bot1-crm` — в репозитории БОТА 1
- для `bot2-consultation` — в этом репозитории

Внутри Docker-сети БОТ 2 должен ходить в БОТ 1 по:

```env
CRM_API_BASE_URL=http://bot1-crm:8000
```

Production-версия с PostgreSQL/Redis и остальными ботами будет добавляться позже.

## Ручная локальная проверка

1. Запустить БОТ 1:

```powershell
uvicorn app.main:app --reload --port 8000
```

2. Запустить БОТ 2:

```powershell
$env:CRM_ADAPTER="http_api"
$env:CRM_API_BASE_URL="http://localhost:8000"
$env:CRM_API_TOKEN="<BOT2_API_TOKEN из БОТА 1, если включен>"
uvicorn app.main:app --reload --port 8002
```

3. В Telegram БОТА 2:

- открыть `Клиенты на консультацию`
- открыть карточку
- сгенерировать аудит
- сформировать предложение
- сгенерировать DOCX
- указать итог консультации

4. В БОТЕ 1 проверить:

- статус компании
- LeadInteraction
- FollowUpTask

## Следующие этапы

- Отдельный proposal DOCX/export для отправки клиенту.
- Более точные шаблоны КП после накопления кейсов и пакетов.
- RBAC для нескольких ролей менеджеров.
- Production compose для всей связки из 5 ботов.

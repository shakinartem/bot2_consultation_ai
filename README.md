# БОТ 2 — SHARiK digital Consultation AI

БОТ 2 помогает менеджеру агентства ШАРиК digital / SPG готовить и проводить консультации со стоматологическими клиниками.

Связка с системой:

- БОТ 1 CRM находит и ведет лидов, фиксирует холодные звонки и переводит подходящих клиентов в статус `consultation_planned`.
- БОТ 2 не парсит клиентов сам. Он получает клиентов из CRM/БОТА 1 через `CRM_ADAPTER`.
- Mock-режим БОТА 2 для локального MVP может продолжать использовать legacy-статус `consultation_scheduled`.
- Менеджер в Telegram открывает карточку клиники, добавляет заметки/ссылки/материалы, генерирует AI-аудит и DOCX, затем фиксирует итог консультации.

## Возможности MVP

- Telegram-first интерфейс для менеджера.
- Список клиентов, готовых к консультации, из CRM/БОТА 1.
- Карточка стоматологической клиники.
- Активная консультация без дублей.
- Заметки, ссылки и материалы клиента.
- AI-аудит сайта, карт, соцсетей и репутации.
- Roadmap на 7/30/90 дней.
- DOCX с айдентикой ШАРиК digital.
- Опциональный PDF export через LibreOffice.
- FastAPI endpoints для будущего web/mini app.
- Mock CRM для локального запуска без внешних сервисов.

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
ADMIN_IDS=123456789,987654321
```

Важно: пустой `ADMIN_IDS` — только dev-режим. В рабочем режиме укажите Telegram ID менеджеров, иначе бот будет доступен всем, кто знает токен.

## Запуск

```powershell
uvicorn app.main:app --reload
```

FastAPI запускает:

- `/health`;
- `/api/*`;
- Telegram polling, если задан `BOT_TOKEN`;
- создание таблиц SQLite через SQLAlchemy metadata.

Если `BOT_TOKEN` пустой, Telegram polling не запускается. Это удобно для smoke/API-проверок: FastAPI стартует, а в лог пишется `Telegram bot disabled: BOT_TOKEN is empty`.

Для миграций:

```powershell
alembic upgrade head
```

## Telegram сценарий

Главное меню:

- 📋 Клиенты на консультацию
- 🔎 Открыть карточку
- 🧠 Сгенерировать аудит
- 📄 Сгенерировать документ
- ✅ Указать результат консультации
- 🗂 Архив консультаций
- ⚙️ Настройки AI
- ❓ Помощь

Рабочий путь менеджера:

1. Нажать `📋 Клиенты на консультацию`.
2. Открыть карточку стоматологии.
3. Добавить заметку, ссылки и материалы.
4. Сгенерировать AI-аудит.
5. Сгенерировать DOCX.
6. Указать итог: отказ, думает, договор отправлен, договор подписан.

При подписании договора статус консультации становится `client`, а CRM adapter получает обновление статуса компании.

## CRM_ADAPTER

Настройка:

```env
CRM_ADAPTER=mock
```

Режимы:

- `mock` / `in_memory` — локальный тестовый режим, работает без внешних зависимостей.
- `http_api` — preferred режим интеграции с реальным API БОТА 1.
- `sqlite_shared` — заготовка для чтения общей SQLite базы БОТА 1.

Интерфейс adapter:

- `list_consultation_scheduled()`
- `get_company(company_id)`
- `update_company_status(company_id, status)`
- `add_interaction(company_id, type, result, notes)`
- `create_task(company_id, title, due_at, notes)`
- `send_consultation_result(company_id, result, notes)` — preferred handoff результата консультации в БОТ 1

Если `http_api` недоступен, бот показывает менеджеру понятную ошибку. Если `sqlite_shared` база отсутствует, бот не падает и возвращает пустые данные.

Если CRM недоступна во время фиксации итога консультации, БОТ 2 всё равно сохраняет локальный результат консультации и показывает предупреждение: CRM/БОТ 1 не обновились. Это значит, что менеджеру нужно повторить синхронизацию или проверить БОТ 1.

Для проверки без БОТА 1 используйте:

```env
CRM_ADAPTER=mock
```

Mock-режим содержит тестовые стоматологии и подходит для локальной демонстрации менеджеру.

## Интеграция с БОТОМ 1

Preferred режим:

```env
CRM_ADAPTER=http_api
CRM_API_BASE_URL=http://localhost:8000
CRM_API_TOKEN=
CRM_READY_STATUSES=consultation_planned,consultation_scheduled
```

Если в БОТЕ 1 заполнен `BOT2_API_TOKEN`, то `CRM_API_TOKEN` в БОТЕ 2 должен совпадать с ним.

Основной handoff контракт:

- БОТ 2 получает клиентов из `GET /api/bot2/consultation-ready`
- БОТ 2 отправляет итог в `POST /api/bot2/companies/{company_id}/consultation-result`

Fallback, если новый handoff API еще не установлен в БОТЕ 1:

- `GET /api/companies?status=consultation_planned&limit=100`
- `PATCH /api/companies/{company_id}` с payload `{"status": "..."}`
- `POST /api/companies/{company_id}/interactions`
- `POST /api/tasks`

Маппинг статусов БОТА 2 -> БОТ 1:

- `signed` / `client` -> `deal_won`
- `contract_sent` -> `proposal_sent`
- `thinking` -> `interested`
- `refused` -> `deal_lost`

Маппинг interaction result БОТА 2 -> БОТ 1:

- `refused` -> `rejected`
- `thinking` -> `interested`
- `contract_sent` -> `proposal_requested`
- `signed` / `client` -> `deal_won`

## API auth

По умолчанию API открыт для локальной разработки:

```env
API_AUTH_ENABLED=false
```

Чтобы защитить `/api/*`, включите:

```env
API_AUTH_ENABLED=true
API_TOKEN=your_internal_token
```

После этого все `/api/*` endpoints требуют header:

```text
Authorization: Bearer your_internal_token
```

`/health` остается публичным. Если `API_AUTH_ENABLED=true`, но `API_TOKEN` пустой, приложение пишет предупреждение в лог, а `/api/*` возвращает ошибку конфигурации.

## AI providers

```env
AI_PROVIDER=fallback
```

Поддерживаются:

- `fallback` — локальный структурированный шаблон, без ключей и сети.
- `openrouter` — OpenRouter chat completions.
- `ollama` — локальный Ollama.

Fallback всегда возвращает markdown-разделы:

- `# Общий вывод`
- `# Аудит сайта`
- `# Аудит карт`
- `# Аудит соцсетей`
- `# Репутация`
- `# Основные проблемы`
- `# Точки роста`
- `# Быстрые улучшения`
- `# План на 7 дней`
- `# План на 30 дней`
- `# План на 90 дней`
- `# Рекомендации по услугам ШАРиК digital`
- `# Следующий шаг`

Prompt builder:

```python
build_consultation_audit_prompt(company_data, extra_data)
```

Он учитывает название клиники, город, сайт, карты, рейтинг, отзывы, соцсети, заметки CRM, боль клиента, результат холодного звонка, заметки менеджера и материалы.

## DOCX/PDF

DOCX создается всегда:

```text
storage/docs/consultation_company_{company_id}_{consultation_id}.docx
```

Структура документа:

- обложка;
- краткое резюме;
- таблица данных клиента;
- аудит сайта, карт, соцсетей и репутации;
- основные проблемы;
- точки роста;
- быстрые улучшения;
- план на 7/30/90 дней;
- рекомендации по услугам ШАРиК digital;
- следующий шаг;
- подвал с позиционированием агентства.

PDF опционален:

```env
PDF_EXPORT_ENABLED=false
PDF_EXPORT_PROVIDER=none
```

Для локального PDF:

```env
PDF_EXPORT_ENABLED=true
PDF_EXPORT_PROVIDER=libreoffice
```

Если LibreOffice недоступен, бот отправит DOCX и сообщит, что PDF недоступен.

## API endpoints

- `GET /health`
- `GET /api/consultations`
- `GET /api/consultations/{consultation_id}`
- `POST /api/consultations`
- `POST /api/consultations/{consultation_id}/notes`
- `POST /api/consultations/{consultation_id}/attachments/link`
- `POST /api/consultations/{consultation_id}/attachments/text`
- `POST /api/consultations/{consultation_id}/generate-audit`
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

Материалы клиента:

```text
storage/clients/company_{id}/
```

`.gitignore` исключает `.env`, SQLite базы и реальные клиентские файлы из `storage`.

## Smoke test

```powershell
py scripts/smoke_test.py
```

Проверяет:

- `/health` доступен без API token;
- `/api/consultations` возвращает `401` без токена, если временно включить `API_AUTH_ENABLED=true`;
- `/api/consultations` доступен с `Authorization: Bearer test-token`, если временно включить `API_AUTH_ENABLED=true`;
- `Company.from_mapping()` корректно читает payload БОТА 1;
- status mapping БОТ 2 -> БОТ 1 корректный;
- interaction payload builder собирает payload под `/api/companies/{company_id}/interactions`;
- task payload builder собирает payload под `POST /api/tasks`;
- mock CRM возвращает клиентов;
- создается consultation;
- fallback audit генерируется и парсится;
- DOCX создается;
- итог консультации обновляет статус и возвращает `warning=None` в mock CRM;
- при падении CRM adapter локальный итог сохраняется, а warning возвращается.

## Финальная локальная проверка

1. Запустите smoke test БОТА 2:

```powershell
py scripts/smoke_test.py
```

2. Запустите БОТ 1:

```powershell
uvicorn app.main:app --reload --port 8000
```

3. Создайте или оставьте в БОТЕ 1 компанию со статусом `consultation_planned`.

4. Запустите БОТ 2:

```powershell
$env:CRM_ADAPTER="http_api"
$env:CRM_API_BASE_URL="http://localhost:8000"
$env:CRM_API_TOKEN="<BOT2_API_TOKEN из БОТА 1, если включен>"
uvicorn app.main:app --reload --port 8002
```

5. В Telegram БОТА 2:

- откройте `Клиенты на консультацию`
- убедитесь, что видна компания из БОТА 1
- откройте карточку
- сгенерируйте аудит
- сгенерируйте DOCX
- укажите итог `Думает` или `Договор отправлен`

6. Проверьте в БОТЕ 1, что обновились:

- статус компании
- interaction
- follow-up task

7. Для локальной API-проверки БОТА 2 отдельно проверьте `GET /health`:

```powershell
curl http://127.0.0.1:8002/health
```

8. Для локальной API auth-проверки БОТА 2:

```powershell
$env:API_AUTH_ENABLED="true"
$env:API_TOKEN="test-token"
uvicorn app.main:app --reload --port 8002
```

В новом окне:

```powershell
curl http://127.0.0.1:8002/api/consultations
curl -H "Authorization: Bearer test-token" http://127.0.0.1:8002/api/consultations
```

9. Если заполнен `BOT_TOKEN`, убедитесь, что Telegram polling стартует вместе с FastAPI и бот отвечает на базовый сценарий менеджера.

## Логирование

Логируются:

- старт/остановка FastAPI;
- отключение Telegram при пустом `BOT_TOKEN`;
- старт/падение Telegram polling;
- ошибки CRM adapter;
- ошибки AI provider и переход на fallback;
- ошибки PDF export.

Секреты `BOT_TOKEN`, `OPENROUTER_API_KEY`, `CRM_API_TOKEN`, `API_TOKEN` не логируются.

## Следующие этапы

- Ручной end-to-end запуск двух ботов на локальном handoff API.
- Полноценные pytest-тесты и test DB fixtures.
- Брендовый PDF export с шаблонами.
- Production bot handoff после подписания договора.
- Roadmap bot для ведения работ.
- Content bot для контента стоматологии.
- Опциональное внешнее хранилище, например Cloudinary, без обязательной зависимости в MVP.

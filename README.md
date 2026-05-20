# БОТ 2 — SHARiK digital Consultation AI

БОТ 2 помогает менеджеру агентства ШАРиК digital / SPG готовить и проводить консультации со стоматологическими клиниками.

Связка с системой:

- БОТ 1 CRM находит и ведет лидов, фиксирует холодные звонки и переводит подходящих клиентов в статус `consultation_scheduled`.
- БОТ 2 не парсит клиентов сам. Он получает клиентов из CRM/БОТА 1 через `CRM_ADAPTER`.
- Менеджер в Telegram открывает карточку клиники, добавляет заметки/ссылки/материалы, генерирует AI-аудит и DOCX, затем фиксирует итог консультации.

## Возможности MVP

- Telegram-first интерфейс для менеджера.
- Список клиентов со статусом `consultation_scheduled`.
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

AI_PROVIDER=fallback

CRM_ADAPTER=mock
CRM_API_BASE_URL=http://localhost:8001
CRM_API_TOKEN=
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
- `http_api` — заготовка для API БОТА 1.
- `sqlite_shared` — заготовка для чтения общей SQLite базы БОТА 1.

Интерфейс adapter:

- `list_consultation_scheduled()`
- `get_company(company_id)`
- `update_company_status(company_id, status)`
- `add_interaction(company_id, type, result, notes)`
- `create_task(company_id, title, due_at, notes)`

Если `http_api` недоступен, бот показывает менеджеру понятную ошибку. Если `sqlite_shared` база отсутствует, бот не падает и возвращает пустые данные.

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

- mock CRM возвращает клиентов;
- создается consultation;
- fallback audit генерируется и парсится;
- DOCX создается;
- итог консультации обновляет статус.

## Следующие этапы

- Реальная интеграция с БОТОМ 1 после согласования схемы/API.
- Полноценные pytest-тесты и test DB fixtures.
- Брендовый PDF export с шаблонами.
- Production bot handoff после подписания договора.
- Roadmap bot для ведения работ.
- Content bot для контента стоматологии.
- Опциональное внешнее хранилище, например Cloudinary, без обязательной зависимости в MVP.

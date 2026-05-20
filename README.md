# SHARiK digital Consultation AI System

MVP Telegram-бота №2 для клиентов, которые прошли квалификацию после холодного звонка.

Бот помогает менеджеру:

- получать клиентов из CRM со статусом `consultation_scheduled`;
- открывать карточку клиента;
- добавлять заметки, ссылки и материалы;
- генерировать AI-аудит сайта, карт, соцсетей и репутации;
- формировать точки роста, рекомендации и roadmap;
- создавать DOCX-документ с айдентикой ШАРиК digital;
- фиксировать результат консультации.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=telegram_bot_token
DATABASE_URL=sqlite+aiosqlite:///./app.db
AI_PROVIDER=fallback
ADMIN_IDS=123456789,987654321
```

Если `ADMIN_IDS` пустой, бот доступен всем, кто знает токен бота. Для рабочего режима лучше указать Telegram ID менеджеров.

## Запуск

```bash
uvicorn app.main:app --reload
```

FastAPI поднимет:

- `/health` для проверки сервиса;
- Telegram polling-бота;
- SQLite-таблицы через `Base.metadata.create_all`.

Для production-подхода можно использовать Alembic:

```bash
alembic upgrade head
```

## AI providers

Провайдер выбирается через `AI_PROVIDER`.

### fallback

```env
AI_PROVIDER=fallback
```

Не требует ключей. Возвращает базовый шаблон аудита, чтобы весь workflow работал сразу.

### OpenRouter

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
```

### Ollama

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

## Генерация аудита

Prompt строится функцией:

```python
build_consultation_audit_prompt(company_data, extra_data)
```

AI должен вернуть разделы:

1. Общий вывод
2. Аудит сайта
3. Аудит карт
4. Аудит соцсетей
5. Репутация
6. Основные проблемы
7. Точки роста
8. Быстрые улучшения
9. План на 7 дней
10. План на 30 дней
11. План на 90 дней
12. Рекомендации по услугам

Из ответа парсятся поля консультации: аудит сайта, карт, соцсетей, репутации, точки роста, рекомендации и roadmap.

## Генерация DOCX

DOCX создается через `python-docx` и сохраняется в:

```text
storage/docs/consultation_company_{company_id}_{consultation_id}.docx
```

Документ содержит:

- обложку `ШАРиК digital`;
- информацию о клиенте;
- краткий вывод;
- сайт;
- карты;
- соцсети;
- репутацию;
- точки роста;
- планы на 7, 30 и 90 дней;
- рекомендации;
- следующий шаг.

## Структура консультации

Основные модели:

- `Consultation`
- `ConsultationNote`
- `ConsultationAttachment`

Статусы консультации:

- `pending`
- `in_progress`
- `completed`
- `refused`
- `thinking`
- `contract_sent`
- `client`

Результаты в боте:

- отказ -> `refused`
- думает -> `thinking`
- договор отправлен -> `contract_sent`
- договор подписан -> `client`

Если договор подписан, CRM-статус компании обновляется на `client`. В коде оставлена архитектурная точка для передачи клиента в production bot.

## CRM

Сейчас CRM реализована как in-memory adapter в `app/modules/crm/service.py`.

Для интеграции с ботом №1 или реальной CRM нужно заменить методы:

- `list_consultation_scheduled`
- `get_company`
- `update_company_status`

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

## Telegram меню

- Клиенты на консультацию
- Открыть карточку
- Добавить заметки
- Добавить ссылки
- Добавить материалы
- Сгенерировать аудит
- Сгенерировать DOCX
- Указать результат консультации
- Архив консультаций
- Настройки AI

## Следующие этапы

- Брендовый PDF-экспорт.
- Cloudinary для хранения материалов и документов.
- Передача клиента в production bot после подписания договора.
- Roadmap bot для ведения работ после консультации.
- Content bot для генерации контента и материалов.

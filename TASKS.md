# TASKS: SHARiK digital Consultation AI Bot

## Общий статус

MVP доведен до рабочего сценария менеджера: FastAPI + Telegram polling bot + SQLite/SQLAlchemy + Alembic + CRM adapter + AI providers + DOCX/PDF-заготовка. Бот готов к локальному использованию с `CRM_ADAPTER=mock`; реальная интеграция с БОТОМ 1 остается следующим этапом после согласования API/схемы.

## Что уже реализовано

- [x] Базовая структура `app/`, `alembic/`, `storage/`, `templates/`.
- [x] FastAPI entrypoint `app.main:app` с `/health`.
- [x] Базовое логирование старта, polling, CRM/AI/PDF ошибок.
- [x] Безопасный старт Telegram polling: пустой `BOT_TOKEN` отключает бот с записью в лог.
- [x] Простая token-защита `/api/*` через `API_AUTH_ENABLED`.
- [x] Telegram bot на aiogram 3.
- [x] SQLAlchemy модели `Consultation`, `ConsultationNote`, `ConsultationAttachment`.
- [x] Alembic initial migration.
- [x] AI abstraction layer: OpenRouter, Ollama, fallback.
- [x] Базовый prompt builder.
- [x] DOCX генератор через `python-docx`.
- [x] `.env.example`, `.gitignore`, README.

## Что доделывается сейчас

- [x] Расширяемый CRM adapter: mock, HTTP API, shared SQLite.
- [x] Улучшенный Telegram UX менеджера.
- [x] Улучшенный стоматологический AI-аудит с markdown-разделами.
- [x] Более коммерческий DOCX с айдентикой ШАРиК digital.
- [x] Опциональная заготовка PDF export.
- [x] FastAPI endpoints для будущих web/mini app и других ботов.
- [x] Smoke test.
- [x] Обновление README.
- [x] Стабилизация ошибок CRM при фиксации результата консультации.
- [x] API endpoints для text/link attachments.

## MVP задачи

- [x] Показывать клиентов `consultation_scheduled` из CRM adapter.
- [x] Открывать карточку стоматологии с полными данными.
- [x] Создавать активную consultation без дублей.
- [x] Сохранять заметки менеджера.
- [x] Сохранять ссылки как структурированные attachments.
- [x] Загружать материалы в `storage/clients/company_{id}/`.
- [x] Генерировать fallback/OpenRouter/Ollama аудит без падения бота.
- [x] Парсить AI-аудит в поля консультации.
- [x] Генерировать DOCX и отправлять менеджеру.
- [x] Фиксировать результат консультации и обновлять CRM adapter.
- [x] Добавлять interaction/task в CRM adapter при результате.
- [x] Дать минимальные API endpoints.
- [x] Smoke test: CRM mock -> consultation -> fallback audit -> DOCX.
- [x] Smoke test: `set_result()` возвращает `warning=None` на mock CRM.
- [x] Smoke test: при падении CRM локальный итог сохраняется, warning возвращается.

## Технический долг

- [ ] Разнести большой `app/bot.py` на routers/services после MVP.
- [ ] Добавить полноценные pytest-тесты и test database fixtures.
- [ ] Добавить structured logging/trace id для production.
- [ ] Добавить persistent CRM integration после доступа к БОТУ 1.
- [ ] Добавить нормальную миграцию данных при смене схемы в production.
- [ ] Добавить централизованное логирование без секретов.
- [ ] Добавить rate limits и более строгие лимиты загрузок.

## Будущие улучшения

- [ ] Брендовый PDF export через LibreOffice.
- [ ] Cloudinary как опциональное внешнее хранилище.
- [ ] Передача клиента в production bot.
- [ ] Roadmap bot для ведения работ после консультации.
- [ ] Content bot для контент-плана и материалов.
- [ ] Web/Telegram Mini App без замены Telegram-first UX.

## Архитектурные заметки

- БОТ 2 не парсит клиентов сам: источник клиентов — CRM/БОТ 1 через `CRMAdapter`.
- По умолчанию `CRM_ADAPTER=mock`, чтобы локальный запуск работал без внешних сервисов.
- `http_api` и `sqlite_shared` работают best-effort: внешняя ошибка должна превращаться в понятное сообщение менеджеру, а не падение процесса.
- `fallback` AI provider должен всегда оставаться рабочим и структурированным.
- DOCX генерируется всегда; PDF только опционально, если доступен локальный конвертер.
- `ADMIN_IDS` пустой только для dev-режима; в рабочем режиме надо ограничивать доступ.
- Основной API живет под `/api/*`; web UI пока не добавляется.

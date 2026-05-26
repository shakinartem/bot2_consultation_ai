# Consultation Assistant Vertical MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved vertical MVP across BOT 1 CRM and BOT 2 Consultation AI: consultation context endpoint, context-aware audit, proposal MVP, richer DOCX, manager access checks, and dev Docker readiness.

**Architecture:** BOT 1 becomes the source of structured sales context via a new `/api/bot2/*` endpoint. BOT 2 consumes that context through `CRMAdapter`, merges it with consultation notes and attachments for audit/proposal generation, stores the new fields in `Consultation`, and reuses the same data for DOCX output. Fallback behavior remains first-class at every layer.

**Tech Stack:** FastAPI, aiogram, SQLAlchemy, Alembic, Pydantic, python-docx, httpx, SQLite, Docker.

---

### Task 1: BOT 1 Consultation Context API

**Files:**
- Modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/app/modules/crm/schemas.py`
- Modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/app/modules/crm/service.py`
- Modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/app/api/routes.py`
- Create: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/scripts/smoke_bot2_context.py`
- Modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/README.md`
- Modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/TASKS.md`

- [ ] Add context schemas for company, decision makers, contacts, interactions, tasks, and the full Bot 2 consultation context response.
- [ ] Implement `build_bot2_consultation_context(session, company_id)` with deterministic sorting and fallback next-step text.
- [ ] Add `GET /api/bot2/companies/{company_id}/consultation-context` inside `bot2_router` with `require_bot2_auth` and `404` handling.
- [ ] Write `scripts/smoke_bot2_context.py` covering auth, company creation, related entities, and response structure.
- [ ] Update BOT 1 docs for the new endpoint and mark the context layer as done.

### Task 2: BOT 2 CRM Adapter Context Integration

**Files:**
- Modify: `app/modules/crm/service.py`
- Modify: `scripts/smoke_test.py`
- Modify: `README.md`

- [ ] Extend `CRMAdapter` with `get_consultation_context(company_id)`.
- [ ] Implement HTTP adapter rich fetch plus minimal fallback on `404`/`5xx`.
- [ ] Implement realistic mock context and minimal/no-op shared SQLite context.
- [ ] Extend smoke coverage to assert context retrieval in mock mode.
- [ ] Update BOT 2 integration docs to describe the new context endpoint and fallback behavior.

### Task 3: BOT 2 Consultation Audit With Sales Context

**Files:**
- Modify: `app/modules/consultation/models.py`
- Create: `alembic/versions/0003_add_consultation_sales_context.py`
- Modify: `app/modules/consultation/service.py`
- Modify: `app/modules/ai/prompts.py`
- Modify: `app/modules/ai/parser.py`
- Modify: `app/schemas.py`
- Modify: `scripts/smoke_test.py`

- [ ] Add `sales_context` and `consultation_talking_points` fields to `Consultation`.
- [ ] Add Alembic migration for the new fields.
- [ ] Merge CRM context, notes, and attachments inside `generate_audit()`.
- [ ] Expand the audit prompt with `# Контекст продаж` and `# Что важно проговорить на консультации` plus stronger factual constraints.
- [ ] Extend parser and API schemas to persist and expose the new sections.
- [ ] Extend smoke coverage to ensure audit generation still works with fallback AI and context present.

### Task 4: BOT 2 Proposal MVP

**Files:**
- Modify: `app/modules/consultation/models.py`
- Create: `alembic/versions/0004_add_consultation_proposal_fields.py`
- Modify: `app/modules/consultation/service.py`
- Modify: `app/modules/ai/prompts.py`
- Modify: `app/modules/ai/parser.py` (if metadata helpers are added there)
- Modify: `app/schemas.py`
- Modify: `app/api.py`
- Modify: `app/bot.py`
- Modify: `scripts/smoke_test.py`

- [ ] Add proposal storage fields to `Consultation`.
- [ ] Add Alembic migration for proposal fields.
- [ ] Implement `generate_proposal(consultation_id)` with AI path and deterministic fallback path using SHARiK digital pricing defaults.
- [ ] Add API endpoint `POST /api/consultations/{consultation_id}/generate-proposal`.
- [ ] Add Telegram button `💼 Сформировать предложение` and `/proposal ID` command without changing the existing UX flow.
- [ ] Parse and persist `proposal_package` and `proposal_budget_range`.
- [ ] Extend smoke coverage for fallback proposal generation and the API endpoint.

### Task 5: BOT 2 Richer DOCX and Branding

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`
- Create: `assets/brand/.gitkeep`
- Create: `assets/brand/README.md`
- Modify: `app/modules/documents/generator.py`
- Modify: `scripts/smoke_test.py`
- Modify: `README.md`

- [ ] Add optional agency branding settings including `AGENCY_LOGO_PATH`.
- [ ] Add brand asset placeholders and instructions.
- [ ] Update DOCX generation to include optional logo, sales context, talking points, proposal section, and footer contacts while using only the SHARiK digital brand.
- [ ] Keep DOCX generation stable when no logo or optional contact fields are present.
- [ ] Extend smoke coverage to verify DOCX generation still succeeds.

### Task 6: Manager Access and Dev Docker Readiness

**Files:**
- Modify: `app/bot.py`
- Modify: `README.md`
- Create: `.dockerignore`
- Create or modify: `Dockerfile.dev`
- Create: `docker/docker-compose.dev.yml`
- Modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/README.md`
- Create: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/.dockerignore`
- Create or modify: `C:/Users/Admin/Desktop/Proga/SHARIK/5bots/1_CRM_bot/Dockerfile.dev`

- [ ] Confirm all Telegram handlers remain behind admin checks and document `ADMIN_IDS` behavior as simple multi-manager access.
- [ ] Add Docker ignore files and dev Dockerfiles for both repos.
- [ ] Add `docker/docker-compose.dev.yml` in BOT 2 for BOT 1 + BOT 2 plus commented placeholders for BOT 3/4/5.
- [ ] Update both READMEs with Docker future/local compose notes and manager access notes.

### Task 7: Verification

**Files:**
- No code files; run commands and update docs only if needed.

- [ ] Run in `bot1_crm`:
  - `python scripts/smoke_bot2_handoff.py`
  - `python scripts/smoke_bot2_context.py`
  - `python scripts/test_digest_module.py`
- [ ] Run in `bot2_consultation_ai`:
  - `python scripts/smoke_test.py`
- [ ] Record any environment blockers accurately if a command cannot pass.
- [ ] Summarize changed files, smoke status, env vars, run commands, and next steps.

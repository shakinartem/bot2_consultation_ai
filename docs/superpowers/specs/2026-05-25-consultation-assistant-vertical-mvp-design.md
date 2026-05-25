# Consultation Assistant Vertical MVP Design

**Date:** 2026-05-25

**Scope:** Extend the existing BOT 1 CRM and BOT 2 Consultation AI integration so BOT 2 can consume full sales context, use that context in the consultation audit, generate a preliminary proposal, produce a richer DOCX, and document a future local Docker compose setup without breaking the current MVP flow.

## Goals

- Keep the current BOT 1 handoff API and BOT 2 Telegram UX working.
- Add a stable BOT 1 endpoint that returns consultation-ready sales context as JSON.
- Make BOT 2 use that context during audit generation with safe fallbacks.
- Add an MVP proposal generation flow in BOT 2 with AI and fallback modes.
- Enrich DOCX output so it is useful both for internal consultation prep and for sending a preliminary client-facing package.
- Prepare both projects for future local Docker compose usage.

## Non-Goals

- No full BOT 3/content workflow.
- No production orchestration, Kubernetes, or multi-service deployment platform.
- No paid external services as mandatory dependencies.
- No removal of mock mode from BOT 2.
- No rewrite of current data models or Telegram interaction model from scratch.

## Constraints

- All secrets stay in `.env` and `.env.example`.
- No real client documents or tokens in git.
- BOT 2 must still work in `CRM_ADAPTER=mock`.
- If a richer integration path is unavailable, BOT 2 must fall back to current minimal company-based behavior.
- New JSON endpoints under `/api/bot2/*` in BOT 1 must keep the existing `BOT2_API_TOKEN` protection.

## Current Baseline

### BOT 1

- Already exposes:
  - `GET /api/bot2/consultation-ready`
  - `POST /api/bot2/companies/{company_id}/consultation-result`
- Already stores the source sales context needed by BOT 2:
  - `Company`
  - `DecisionMaker`
  - `ContactPoint`
  - `LeadInteraction`
  - `FollowUpTask`
- Already has helper logic that computes a next step and formats consultation package text.

### BOT 2

- Already has `CRMAdapter` with `mock`, `http_api`, and `sqlite_shared`.
- Already creates consultations, notes, attachments, AI audit, DOCX, and writes consultation result back to BOT 1.
- Already has fallback AI behavior when the primary provider fails.
- Does not yet have a structured concept of external sales context beyond the base company payload.

## Proposed Architecture

Implementation is split into four dependent layers.

### Layer 1: BOT 1 Consultation Context Endpoint

Add:

- `GET /api/bot2/companies/{company_id}/consultation-context`

Behavior:

- Implement in `app/api/routes.py` under `bot2_router`.
- Reuse `require_bot2_auth`.
- Build the response through a new service function:
  - `build_bot2_consultation_context(session, company_id)`

Response shape:

- `company`
- `decision_makers`
- `contacts`
- `recent_interactions`
- `open_tasks`
- `latest_proposal`
- `latest_call_result`
- `recommended_next_step`
- `sales_summary`

Design choices:

- Use the already loaded SQLAlchemy relationships from `Company`.
- Keep sorting rules simple and deterministic:
  - `recent_interactions`: last 10-15 by `created_at desc`
  - `open_tasks`: all open tasks ordered by `due_at asc nulls last`
- `recommended_next_step`:
  - first open task title
  - else latest interaction `next_action`
  - else fixed fallback string
- `sales_summary` is plain deterministic text assembled from CRM facts, not AI-generated.

### Layer 2: BOT 2 Context-Aware Audit

Extend `CRMAdapter`:

- `async def get_consultation_context(company_id: int) -> dict[str, Any] | None`

Adapter behavior:

- Base `CRMAdapter`: returns `None`
- `HTTPCRMAdapter`:
  - try `GET /api/bot2/companies/{company_id}/consultation-context`
  - on `404` or `5xx`, fall back to `get_company()` and synthesize a minimal context
- `MockCRMAdapter`:
  - returns a realistic structured context
- `SharedSQLiteCRMAdapter`:
  - returns `None` or a minimal context only

Audit generation:

- `ConsultationService.generate_audit()` fetches:
  - company
  - consultation notes
  - attachments
  - CRM consultation context
- Prompt builder receives a single merged payload with explicit sections.
- Prompt must clearly distinguish:
  - confirmed CRM facts
  - manager-added materials
  - missing data / assumptions

Prompt additions:

- `# Контекст продаж`
- `# Что важно проговорить на консультации`

Parser/model changes:

- Add consultation fields for:
  - `sales_context`
  - `consultation_talking_points`
- Add Alembic migration if fields are introduced.

### Layer 3: BOT 2 Proposal MVP and Richer DOCX

Proposal generation:

- Add consultation fields:
  - `proposal_text`
  - `proposal_package`
  - `proposal_budget_range`
  - `proposal_document_path`
- Add Alembic migration.
- Add `ConsultationService.generate_proposal(consultation_id)`.
- Add API endpoint:
  - `POST /api/consultations/{consultation_id}/generate-proposal`
- Add Telegram entrypoints:
  - button `💼 Сформировать предложение`
  - command `/proposal ID`

Proposal generation inputs:

- CRM company
- CRM consultation context
- audit fields
- notes and attachments

Proposal generation outputs:

- markdown/text using fixed section headers
- extracted lightweight metadata:
  - recommended package
  - budget range

Fallback behavior:

- If AI is unavailable, generate a deterministic proposal from:
  - status
  - main problems
  - growth points
  - recommendations
  - package defaults

DOCX behavior:

- Keep `generate_consultation_docx()` as the main entrypoint.
- Expand document sections to include:
  - cover
  - client data
  - sales context
  - main audit findings
  - 7/30/90 roadmap
  - preliminary proposal
  - next step
  - footer with agency branding from config
- Optional branding settings come from env.
- Missing logo or branding assets must not break DOCX generation.

### Layer 4: Dev Docker Readiness

For both repos:

- add `Dockerfile.dev` if needed
- add `.dockerignore`
- add README section for future local compose use

Compose direction:

- BOT 1 service exposed as `bot1-crm`
- BOT 2 service uses:
  - `CRM_ADAPTER=http_api`
  - `CRM_API_BASE_URL=http://bot1-crm:8000`

The compose setup is documentation/dev-oriented, not a mandatory production runtime.

## Data Model Changes

### BOT 1

No required schema changes for the consultation context endpoint itself.

### BOT 2

Expected consultation additions:

- `sales_context: Text | None`
- `consultation_talking_points: Text | None`
- `proposal_text: Text | None`
- `proposal_package: String | None`
- `proposal_budget_range: String | None`
- `proposal_document_path: String | None`

Agency settings:

- `AGENCY_NAME`
- `AGENCY_PHONE`
- `AGENCY_TELEGRAM`
- `AGENCY_EMAIL`
- `AGENCY_WEBSITE`
- `AGENCY_CITY`

These are optional and only improve output formatting.

## Error Handling and Fallbacks

- BOT 1 context endpoint returns `404` if company is missing.
- BOT 2 `HTTPCRMAdapter.get_consultation_context()`:
  - returns rich context when available
  - returns synthesized minimal context on recoverable endpoint failures
  - does not block audit generation if context cannot be loaded
- Audit generation:
  - uses fallback AI provider if primary AI fails
  - still works when CRM context is partial
- Proposal generation:
  - uses fallback proposal builder if AI fails
- DOCX generation:
  - still succeeds without logo, proposal metadata, or optional agency contacts

## Testing Strategy

### BOT 1

- Add `scripts/smoke_bot2_context.py`
- Keep:
  - `scripts/smoke_bot2_handoff.py`
  - `scripts/test_digest_module.py`

### BOT 2

- Extend `scripts/smoke_test.py` to verify:
  - mock consultation context
  - context-aware audit prompt path
  - fallback audit path with context
  - proposal generation path
  - DOCX generation path

Testing style:

- Prefer focused smoke/regression coverage over broad refactors.
- Validate the new vertical flow end-to-end before pushing.

## Delivery Order

1. BOT 1 consultation context endpoint and smoke.
2. BOT 2 adapter/context-aware audit integration and smoke updates.
3. BOT 2 proposal generation, storage fields, API, Telegram entrypoint, and DOCX upgrade.
4. Docker/dev documentation and files.

## Risks

- BOT 1 lives outside the current writable root, so cross-repo edits may require escalated filesystem operations during implementation.
- BOT 2 already has local uncommitted proposal-related work (`.env.example`, `app/modules/crm/models.py`, `app/modules/proposals/`, `scripts/smoke_proposals.py`), so implementation must avoid overwriting or reverting user work.
- Existing Russian text contains encoding inconsistencies in several files; new changes should avoid expanding the blast radius unless directly required.

## Success Criteria

- BOT 1 returns stable consultation context JSON for consultation-ready companies.
- BOT 2 audit meaningfully incorporates sales context and still works in mock mode.
- BOT 2 can generate a preliminary proposal and save it to the consultation.
- DOCX includes sales context and proposal sections.
- Both repos document the future local Docker compose setup.
- Required smoke scripts run successfully or any blockers are explicitly reported with evidence.

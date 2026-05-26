from __future__ import annotations

import asyncio
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./app_smoke.db")
os.environ.setdefault("AI_PROVIDER", "fallback")
os.environ.setdefault("CRM_ADAPTER", "mock")
os.environ.setdefault("STORAGE_PATH", "./storage")
os.environ["BOT_TOKEN"] = ""

from app.database import AsyncSessionLocal, init_db  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.ai.parser import parse_audit_text  # noqa: E402
from app.modules.ai.providers import FallbackProvider  # noqa: E402
from app.modules.consultation.service import ConsultationService  # noqa: E402
from app.modules.crm.service import (  # noqa: E402
    CRMAdapter,
    CRMAdapterError,
    Company,
    build_bot1_interaction_payload,
    build_bot1_task_payload,
    crm_service,
    map_bot2_status_to_bot1,
)
from app.modules.documents.generator import generate_consultation_docx  # noqa: E402
from app.modules.files.storage import ensure_storage_layout  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class FailingCRMAdapter(CRMAdapter):
    async def list_consultation_scheduled(self) -> list[Company]:
        return []

    async def get_company(self, company_id: int) -> Company | None:
        return None

    async def update_company_status(self, company_id: int, status: str) -> None:
        raise CRMAdapterError("smoke CRM failure")

    async def add_interaction(
        self,
        company_id: int,
        type: str,
        result: str,
        notes: str | None = None,
    ) -> None:
        raise CRMAdapterError("smoke CRM failure")

    async def create_task(
        self,
        company_id: int,
        title: str,
        due_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        raise CRMAdapterError("smoke CRM failure")


@contextmanager
def temporary_env(**updates: str):
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        get_settings.cache_clear()
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


async def main() -> None:
    smoke_db = ROOT / "app_smoke.db"
    if smoke_db.exists():
        smoke_db.unlink()

    company_from_bot1 = Company.from_mapping(
        {
            "id": 501,
            "name": "Стоматология BOT1 Payload",
            "legal_name": 'ООО "Бот 1"',
            "city": "Саратов",
            "region": "Саратовская область",
            "address": "ул. Радищева, 1",
            "phone": "+7 900 123-45-67",
            "website": "https://bot1-clinic.example",
            "social_links": "https://vk.com/bot1clinic, https://bot1.site/social",
            "maps_url": "https://yandex.ru/maps/org/bot1clinic",
            "vk_url": "https://vk.com/bot1clinic",
            "instagram_url": "https://instagram.com/bot1clinic",
            "telegram_url": "https://t.me/bot1clinic",
            "other_socials": "https://youtube.com/@bot1clinic",
            "rating": 4.8,
            "reviews_count": 52,
            "source": "crm",
            "status": "consultation_planned",
            "priority": "high",
            "notes": "Клиника готова к консультации, просит показать точки роста.",
        }
    )
    assert company_from_bot1.status == "consultation_planned", "bot1 company payload must preserve consultation_planned status"
    assert company_from_bot1.niche == "dentistry", "bot1 company payload must default niche to dentistry"
    assert company_from_bot1.crm_notes, "bot1 company payload must map notes into crm_notes"
    assert company_from_bot1.pain == company_from_bot1.crm_notes, "pain may fallback to bot1 notes for MVP"
    assert company_from_bot1.cold_call_result == company_from_bot1.crm_notes, "cold call result may fallback to bot1 notes for MVP"
    assert "https://vk.com/bot1clinic" in company_from_bot1.social_links, "social links must include vk_url"
    assert "https://t.me/bot1clinic" in company_from_bot1.social_links, "social links must include telegram_url"
    assert "https://youtube.com/@bot1clinic" in company_from_bot1.social_links, "social links must include other_socials"

    assert map_bot2_status_to_bot1("client") == "deal_won", "client must map to deal_won for bot1"
    assert map_bot2_status_to_bot1("contract_sent") == "proposal_sent", "contract_sent must map to proposal_sent for bot1"
    assert map_bot2_status_to_bot1("thinking") == "interested", "thinking must map to interested for bot1"
    assert map_bot2_status_to_bot1("refused") == "deal_lost", "refused must map to deal_lost for bot1"

    interaction_payload = build_bot1_interaction_payload("contract_sent", "Договор отправлен после консультации")
    assert interaction_payload == {
        "type": "consultation",
        "result": "proposal_requested",
        "summary": "Договор отправлен после консультации",
        "created_by": "bot2",
    }, "bot1 interaction payload must use consultation/proposal_requested/summary/created_by"

    task_payload = build_bot1_task_payload(
        501,
        "Проверить статус договора",
        datetime(2026, 5, 21, 15, 30, 0),
        "Договор отправлен после консультации",
    )
    assert task_payload == {
        "company_id": 501,
        "title": "Проверить статус договора",
        "description": "Договор отправлен после консультации",
        "due_at": "2026-05-21T15:30:00",
    }, "bot1 task payload must use POST /api/tasks contract"

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200, "/health must be public and return 200"

        with temporary_env(API_AUTH_ENABLED="true", API_TOKEN="test-token"):
            unauthorized = client.get("/api/consultations")
            assert unauthorized.status_code == 401, "/api/consultations must require token when API auth is enabled"

            authorized = client.get(
                "/api/consultations",
                headers={"Authorization": "Bearer test-token"},
            )
            assert authorized.status_code == 200, "/api/consultations must accept a valid bearer token"

        ensure_storage_layout()
        await init_db()

        companies = await crm_service.list_consultation_scheduled()
        assert companies, "mock CRM must return companies ready for consultation"
        company = companies[0]

        async with AsyncSessionLocal() as session:
            service = ConsultationService(session, ai_provider=FallbackProvider())
            consultation = await service.get_or_create_for_company(company.id)
            crm_context = await crm_service.get_consultation_context(company.id)
            assert crm_context, "mock CRM must return consultation context"
            assert crm_context["sales_summary"], "mock consultation context must include sales_summary"
            assert crm_context["recommended_next_step"], "mock consultation context must include recommended_next_step"
            consultation, audit_text = await service.generate_audit(consultation.id)
            parsed = parse_audit_text(audit_text)
            assert parsed["sales_context"], "audit parser must extract sales context"
            assert parsed["consultation_talking_points"], "audit parser must extract consultation talking points"
            assert parsed["overall_conclusion"], "audit parser must extract overall conclusion"
            assert parsed["recommendations"], "audit parser must extract recommendations"

            consultation, proposal_text = await service.generate_proposal(consultation.id)
            assert consultation.proposal_text, "proposal text must be saved"
            assert consultation.proposal_package, "proposal package must be extracted"
            assert consultation.proposal_budget_range, "proposal budget must be extracted"
            assert "# Рекомендуемый пакет" in proposal_text, "proposal text must contain required sections"

            docx_path = await generate_consultation_docx(session, consultation, company)
            assert Path(docx_path).exists(), f"DOCX was not created: {docx_path}"

            consultation, warning = await service.set_result(consultation.id, "thinking", "Smoke test result")
            assert warning is None, "mock CRM must update without warning"
            assert consultation.status == "thinking", "consultation result must update status"

            failing_service = ConsultationService(session, crm=FailingCRMAdapter(), ai_provider=FallbackProvider())
            failing_consultation = await failing_service.create(company.id)
            failing_consultation, warning = await failing_service.set_result(
                failing_consultation.id,
                "contract_sent",
                "CRM failure smoke test",
            )
            assert failing_consultation.status == "contract_sent", "local result must be saved even if CRM fails"
            assert warning, "CRM failure must return a warning"

        proposal_api = client.post("/api/consultations/1/generate-proposal")
        assert proposal_api.status_code == 200, "proposal API endpoint must work"
        assert proposal_api.json()["proposal_text"], "proposal API must return generated proposal text"

    print("Smoke test passed")
    print(f"Company: {company.name}")
    print(f"DOCX: {docx_path}")


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./app_smoke.db")
os.environ.setdefault("AI_PROVIDER", "fallback")
os.environ.setdefault("CRM_ADAPTER", "mock")
os.environ.setdefault("STORAGE_PATH", "./storage")

from app.database import AsyncSessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.ai.parser import parse_audit_text  # noqa: E402
from app.modules.ai.providers import FallbackProvider  # noqa: E402
from app.modules.consultation.service import ConsultationService  # noqa: E402
from app.modules.crm.service import CRMAdapter, CRMAdapterError, Company, crm_service  # noqa: E402
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


async def main() -> None:
    smoke_db = ROOT / "app_smoke.db"
    if smoke_db.exists():
        smoke_db.unlink()

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200, "/health must be public and return 200"

    ensure_storage_layout()
    await init_db()

    companies = await crm_service.list_consultation_scheduled()
    assert companies, "mock CRM must return consultation_scheduled companies"
    company = companies[0]

    async with AsyncSessionLocal() as session:
        service = ConsultationService(session, ai_provider=FallbackProvider())
        consultation = await service.get_or_create_for_company(company.id)
        consultation, audit_text = await service.generate_audit(consultation.id)
        parsed = parse_audit_text(audit_text)
        assert parsed["overall_conclusion"], "audit parser must extract overall conclusion"
        assert parsed["recommendations"], "audit parser must extract recommendations"

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

    print("Smoke test passed")
    print(f"Company: {company.name}")
    print(f"DOCX: {docx_path}")


if __name__ == "__main__":
    asyncio.run(main())

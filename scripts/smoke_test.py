from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./app_smoke.db")
os.environ.setdefault("AI_PROVIDER", "fallback")
os.environ.setdefault("CRM_ADAPTER", "mock")
os.environ.setdefault("STORAGE_PATH", "./storage")

from app.database import AsyncSessionLocal, init_db  # noqa: E402
from app.modules.ai.parser import parse_audit_text  # noqa: E402
from app.modules.ai.providers import FallbackProvider  # noqa: E402
from app.modules.consultation.service import ConsultationService  # noqa: E402
from app.modules.crm.service import crm_service  # noqa: E402
from app.modules.documents.generator import generate_consultation_docx  # noqa: E402
from app.modules.files.storage import ensure_storage_layout  # noqa: E402


async def main() -> None:
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

        consultation = await service.set_result(consultation.id, "thinking", "Smoke test result")
        assert consultation.status == "thinking", "consultation result must update status"

    print("Smoke test passed")
    print(f"Company: {company.name}")
    print(f"DOCX: {docx_path}")


if __name__ == "__main__":
    asyncio.run(main())

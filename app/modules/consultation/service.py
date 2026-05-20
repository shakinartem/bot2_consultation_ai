from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.parser import parse_audit_text
from app.modules.ai.prompts import build_consultation_audit_prompt
from app.modules.ai.providers import AIProvider, get_ai_provider
from app.modules.consultation.models import (
    Consultation,
    ConsultationAttachment,
    ConsultationNote,
    ConsultationStatus,
)
from app.modules.crm.service import CRMService, crm_service


class ConsultationService:
    def __init__(
        self,
        session: AsyncSession,
        crm: CRMService = crm_service,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self.session = session
        self.crm = crm
        self.ai_provider = ai_provider or get_ai_provider()

    async def get_or_create_for_company(self, company_id: int) -> Consultation:
        consultation = await self.get_by_company_id(company_id)
        if consultation is not None:
            return consultation
        consultation = Consultation(company_id=company_id, status=ConsultationStatus.pending.value)
        self.session.add(consultation)
        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation

    async def get_by_company_id(self, company_id: int) -> Consultation | None:
        result = await self.session.execute(
            select(Consultation).where(Consultation.company_id == company_id).order_by(Consultation.id.desc())
        )
        return result.scalars().first()

    async def get(self, consultation_id: int) -> Consultation | None:
        return await self.session.get(Consultation, consultation_id)

    async def list_archive(self) -> list[Consultation]:
        result = await self.session.execute(
            select(Consultation)
            .where(Consultation.status.in_([ConsultationStatus.completed.value, ConsultationStatus.refused.value, ConsultationStatus.client.value]))
            .order_by(Consultation.updated_at.desc())
            .limit(20)
        )
        return list(result.scalars().all())

    async def add_note(self, consultation_id: int, content: str) -> ConsultationNote:
        note = ConsultationNote(consultation_id=consultation_id, content=content)
        self.session.add(note)
        await self.session.commit()
        await self.session.refresh(note)
        return note

    async def add_attachment(self, consultation_id: int, file_path: str, attachment_type: str) -> ConsultationAttachment:
        attachment = ConsultationAttachment(
            consultation_id=consultation_id,
            file_path=file_path,
            type=attachment_type,
        )
        self.session.add(attachment)
        await self.session.commit()
        await self.session.refresh(attachment)
        return attachment

    async def generate_audit(self, consultation_id: int, extra_data: dict | None = None) -> tuple[Consultation, str]:
        consultation = await self.get(consultation_id)
        if consultation is None:
            raise ValueError("Consultation not found")
        company = await self.crm.get_company(consultation.company_id)
        if company is None:
            raise ValueError("Company not found")

        prompt = build_consultation_audit_prompt(asdict(company), extra_data)
        audit_text = await self.ai_provider.generate(prompt)
        parsed = parse_audit_text(audit_text)
        for field, value in parsed.items():
            setattr(consultation, field, value)
        consultation.status = ConsultationStatus.in_progress.value
        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation, audit_text

    async def set_result(self, consultation_id: int, result: str) -> Consultation:
        consultation = await self.get(consultation_id)
        if consultation is None:
            raise ValueError("Consultation not found")

        result_to_status = {
            "refused": ConsultationStatus.refused.value,
            "thinking": ConsultationStatus.thinking.value,
            "contract_sent": ConsultationStatus.contract_sent.value,
            "signed": ConsultationStatus.client.value,
        }
        consultation.status = result_to_status[result]

        if result == "signed":
            await self.crm.update_company_status(consultation.company_id, "client")
        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation

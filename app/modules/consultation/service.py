from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.parser import parse_audit_text, parse_proposal_text
from app.modules.ai.prompts import build_consultation_audit_prompt, build_fallback_proposal_text, build_proposal_prompt
from app.modules.ai.providers import AIProvider, AIProviderError, FallbackProvider, get_ai_provider
from app.modules.consultation.models import (
    Consultation,
    ConsultationAttachment,
    ConsultationNote,
    ConsultationStatus,
)
from app.modules.crm.service import CRMAdapter, CRMAdapterError, crm_service


logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {
    ConsultationStatus.pending.value,
    ConsultationStatus.in_progress.value,
    ConsultationStatus.thinking.value,
    ConsultationStatus.contract_sent.value,
}


class ConsultationService:
    def __init__(
        self,
        session: AsyncSession,
        crm: CRMAdapter = crm_service,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self.session = session
        self.crm = crm
        self.ai_provider = ai_provider or get_ai_provider()

    async def create(self, company_id: int, status: str = ConsultationStatus.pending.value) -> Consultation:
        consultation = Consultation(company_id=company_id, status=status)
        self.session.add(consultation)
        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation

    async def list(self, limit: int = 50) -> list[Consultation]:
        result = await self.session.execute(
            select(Consultation).order_by(Consultation.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create_for_company(self, company_id: int) -> Consultation:
        consultation = await self.get_active_by_company_id(company_id)
        if consultation is not None:
            return consultation
        return await self.create(company_id)

    async def get_active_by_company_id(self, company_id: int) -> Consultation | None:
        result = await self.session.execute(
            select(Consultation)
            .where(Consultation.company_id == company_id)
            .where(Consultation.status.in_(ACTIVE_STATUSES))
            .order_by(Consultation.id.desc())
        )
        return result.scalars().first()

    async def get_by_company_id(self, company_id: int) -> Consultation | None:
        result = await self.session.execute(
            select(Consultation).where(Consultation.company_id == company_id).order_by(Consultation.id.desc())
        )
        return result.scalars().first()

    async def get(self, consultation_id: int) -> Consultation | None:
        return await self.session.get(Consultation, consultation_id)

    async def get_with_relations(self, consultation_id: int) -> Consultation | None:
        result = await self.session.execute(
            select(Consultation)
            .where(Consultation.id == consultation_id)
            .options(selectinload(Consultation.notes), selectinload(Consultation.attachments))
        )
        return result.scalars().first()

    async def list_archive(self) -> list[Consultation]:
        result = await self.session.execute(
            select(Consultation)
            .where(
                Consultation.status.in_(
                    [
                        ConsultationStatus.completed.value,
                        ConsultationStatus.refused.value,
                        ConsultationStatus.client.value,
                    ]
                )
            )
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

    async def _extra_audit_context(self, consultation_id: int) -> dict[str, list[str]]:
        consultation = await self.get_with_relations(consultation_id)
        if consultation is None:
            return {"notes": [], "attachments": []}
        return {
            "notes": [note.content for note in consultation.notes[-10:]],
            "attachments": [
                f"{attachment.type}: {attachment.file_path}"
                for attachment in consultation.attachments[-10:]
            ],
        }

    async def _build_generation_context(self, consultation: Consultation) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        company = await self.crm.get_company(consultation.company_id)
        if company is None:
            raise ValueError("Company not found")
        extra_context = await self._extra_audit_context(consultation.id)
        crm_context = await self.crm.get_consultation_context(consultation.company_id) or {}
        return asdict(company), extra_context, crm_context

    async def generate_audit(self, consultation_id: int, extra_data: dict | None = None) -> tuple[Consultation, str]:
        consultation = await self.get(consultation_id)
        if consultation is None:
            raise ValueError("Consultation not found")
        company_data, context, crm_context = await self._build_generation_context(consultation)
        if extra_data:
            context.update(extra_data)
        prompt = build_consultation_audit_prompt(company_data, context, crm_context)
        try:
            audit_text = await self.ai_provider.generate(prompt)
        except AIProviderError as exc:
            logger.warning("AI provider failed for consultation %s, using fallback: %s", consultation_id, exc)
            audit_text = await FallbackProvider().generate(prompt)

        parsed = parse_audit_text(audit_text)
        for field, value in parsed.items():
            if hasattr(consultation, field):
                setattr(consultation, field, value)
        consultation.status = ConsultationStatus.in_progress.value
        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation, audit_text

    async def generate_proposal(self, consultation_id: int) -> tuple[Consultation, str]:
        consultation = await self.get(consultation_id)
        if consultation is None:
            raise ValueError("Consultation not found")

        company_data, extra_context, crm_context = await self._build_generation_context(consultation)
        consultation_data = {
            "overall_conclusion": consultation.overall_conclusion,
            "main_problems": consultation.main_problems,
            "growth_points": consultation.growth_points,
            "quick_improvements": consultation.quick_improvements,
            "recommendations": consultation.recommendations,
            "roadmap_7_days": consultation.roadmap_7_days,
            "roadmap_30_days": consultation.roadmap_30_days,
            "roadmap_90_days": consultation.roadmap_90_days,
            "next_step": consultation.next_step,
            "sales_context": consultation.sales_context,
            "consultation_talking_points": consultation.consultation_talking_points,
            "result_summary": consultation.result_summary,
        }

        prompt = build_proposal_prompt(company_data, consultation_data, crm_context, extra_context)
        if isinstance(self.ai_provider, FallbackProvider):
            proposal_text = build_fallback_proposal_text(company_data, consultation_data, crm_context)
        else:
            try:
                proposal_text = await self.ai_provider.generate(prompt)
            except AIProviderError as exc:
                logger.warning("AI provider failed for proposal %s, using fallback: %s", consultation_id, exc)
                proposal_text = build_fallback_proposal_text(company_data, consultation_data, crm_context)

        parsed = parse_proposal_text(proposal_text)
        consultation.proposal_text = proposal_text
        consultation.proposal_package = parsed.get("proposal_package")
        consultation.proposal_budget_range = parsed.get("proposal_budget_range")
        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation, proposal_text

    async def set_result(self, consultation_id: int, result: str, notes: str | None = None) -> tuple[Consultation, str | None]:
        consultation = await self.get(consultation_id)
        if consultation is None:
            raise ValueError("Consultation not found")

        result_to_status = {
            "refused": ConsultationStatus.refused.value,
            "thinking": ConsultationStatus.thinking.value,
            "contract_sent": ConsultationStatus.contract_sent.value,
            "signed": ConsultationStatus.client.value,
        }
        if result not in result_to_status:
            raise ValueError("Unknown result")

        consultation.status = result_to_status[result]
        consultation.result_summary = notes or result

        if notes:
            self.session.add(ConsultationNote(consultation_id=consultation_id, content=f"Итог консультации: {notes}"))

        warning: str | None = None
        try:
            await self.crm.send_consultation_result(consultation.company_id, result, notes)
        except CRMAdapterError as exc:
            warning = (
                "Локальный итог консультации сохранен, но CRM/БОТ 1 не обновились. "
                f"Причина: {exc}"
            )
            logger.warning(
                "CRM update failed after local consultation result save: consultation_id=%s company_id=%s result=%s error=%s",
                consultation_id,
                consultation.company_id,
                result,
                exc,
            )

        await self.session.commit()
        await self.session.refresh(consultation)
        return consultation, warning

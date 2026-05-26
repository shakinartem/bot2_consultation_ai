from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.modules.consultation.service import ConsultationService
from app.modules.crm.service import CRMAdapterError, crm_service
from app.modules.documents.generator import generate_consultation_docx
from app.modules.documents.pdf import export_pdf_if_available
from app.schemas import (
    AttachmentCreate,
    AttachmentRead,
    AuditResponse,
    CompanyRead,
    ConsultationCreate,
    ConsultationRead,
    DocumentResponse,
    NoteCreate,
    NoteRead,
    ProposalResponse,
    ResultCreate,
    ResultResponse,
)


async def require_api_auth(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_auth_enabled:
        return
    if not settings.api_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API auth is enabled but API_TOKEN is not configured")
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")


router = APIRouter(prefix="/api", dependencies=[Depends(require_api_auth)])


@router.get("/consultations", response_model=list[ConsultationRead])
async def list_consultations(session: AsyncSession = Depends(get_session)) -> list:
    return await ConsultationService(session).list()


@router.get("/consultations/{consultation_id}", response_model=ConsultationRead)
async def get_consultation(consultation_id: int, session: AsyncSession = Depends(get_session)):
    consultation = await ConsultationService(session).get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.post("/consultations", response_model=ConsultationRead)
async def create_consultation(payload: ConsultationCreate, session: AsyncSession = Depends(get_session)):
    try:
        company = await crm_service.get_company(payload.company_id)
    except CRMAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found in CRM")
    return await ConsultationService(session).get_or_create_for_company(payload.company_id)


@router.post("/consultations/{consultation_id}/notes", response_model=NoteRead)
async def add_note(consultation_id: int, payload: NoteCreate, session: AsyncSession = Depends(get_session)):
    service = ConsultationService(session)
    consultation = await service.get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return await service.add_note(consultation_id, payload.content)


@router.post("/consultations/{consultation_id}/attachments/link", response_model=AttachmentRead)
async def add_link_attachment(consultation_id: int, payload: AttachmentCreate, session: AsyncSession = Depends(get_session)):
    if payload.type != "link":
        raise HTTPException(status_code=400, detail="Payload type must be link")
    service = ConsultationService(session)
    consultation = await service.get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return await service.add_attachment(consultation_id, payload.value, "link")


@router.post("/consultations/{consultation_id}/attachments/text", response_model=AttachmentRead)
async def add_text_attachment(consultation_id: int, payload: AttachmentCreate, session: AsyncSession = Depends(get_session)):
    if payload.type != "text":
        raise HTTPException(status_code=400, detail="Payload type must be text")
    service = ConsultationService(session)
    consultation = await service.get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return await service.add_attachment(consultation_id, payload.value, "text")


@router.post("/consultations/{consultation_id}/generate-audit", response_model=AuditResponse)
async def generate_audit(consultation_id: int, session: AsyncSession = Depends(get_session)):
    try:
        consultation, audit_text = await ConsultationService(session).generate_audit(consultation_id)
    except CRMAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AuditResponse(consultation=consultation, audit_text=audit_text)


@router.post("/consultations/{consultation_id}/generate-docx", response_model=DocumentResponse)
async def generate_docx(consultation_id: int, session: AsyncSession = Depends(get_session)):
    service = ConsultationService(session)
    consultation = await service.get(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    try:
        company = await crm_service.get_company(consultation.company_id)
    except CRMAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found in CRM")

    docx_path = await generate_consultation_docx(session, consultation, company)
    pdf_result = export_pdf_if_available(Path(docx_path))
    if pdf_result.path:
        consultation.pdf_path = str(pdf_result.path)
        await session.commit()
        await session.refresh(consultation)
    return DocumentResponse(
        consultation=consultation,
        document_path=str(docx_path),
        pdf_path=str(pdf_result.path) if pdf_result.path else None,
        pdf_message=pdf_result.message,
    )


@router.post("/consultations/{consultation_id}/generate-proposal", response_model=ProposalResponse)
async def generate_proposal(consultation_id: int, session: AsyncSession = Depends(get_session)):
    try:
        consultation, proposal_text = await ConsultationService(session).generate_proposal(consultation_id)
    except CRMAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProposalResponse(consultation=consultation, proposal_text=proposal_text)


@router.post("/consultations/{consultation_id}/result", response_model=ResultResponse)
async def set_result(consultation_id: int, payload: ResultCreate, session: AsyncSession = Depends(get_session)):
    try:
        consultation, warning = await ConsultationService(session).set_result(consultation_id, payload.result, payload.notes)
        return ResultResponse(consultation=consultation, warning=warning)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/crm/consultation-scheduled", response_model=list[CompanyRead])
async def crm_consultation_scheduled():
    try:
        return await crm_service.list_consultation_scheduled()
    except CRMAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/crm/companies/{company_id}", response_model=CompanyRead)
async def crm_company(company_id: int):
    try:
        company = await crm_service.get_company(company_id)
    except CRMAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

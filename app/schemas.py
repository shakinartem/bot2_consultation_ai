from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyRead(BaseModel):
    id: int
    name: str
    status: str
    niche: str
    city: str
    legal_name: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    maps_url: str | None = None
    social_links: list[str] = []
    rating: float | None = None
    reviews_count: int | None = None
    reputation_notes: str | None = None
    crm_notes: str | None = None
    pain: str | None = None
    cold_call_result: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ConsultationCreate(BaseModel):
    company_id: int


class NoteCreate(BaseModel):
    content: str


class ResultCreate(BaseModel):
    result: str
    notes: str | None = None


class ConsultationRead(BaseModel):
    id: int
    company_id: int
    status: str
    overall_conclusion: str | None = None
    website_audit: str | None = None
    maps_audit: str | None = None
    social_audit: str | None = None
    reputation_audit: str | None = None
    main_problems: str | None = None
    growth_points: str | None = None
    quick_improvements: str | None = None
    recommendations: str | None = None
    roadmap_7_days: str | None = None
    roadmap_30_days: str | None = None
    roadmap_90_days: str | None = None
    next_step: str | None = None
    result_summary: str | None = None
    document_path: str | None = None
    pdf_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoteRead(BaseModel):
    id: int
    consultation_id: int
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditResponse(BaseModel):
    consultation: ConsultationRead
    audit_text: str


class DocumentResponse(BaseModel):
    consultation: ConsultationRead
    document_path: str
    pdf_path: str | None = None
    pdf_message: str

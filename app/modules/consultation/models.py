from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConsultationStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    refused = "refused"
    thinking = "thinking"
    contract_sent = "contract_sent"
    client = "client"


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), default=ConsultationStatus.pending.value)
    overall_conclusion: Mapped[str | None] = mapped_column(Text)
    website_audit: Mapped[str | None] = mapped_column(Text)
    maps_audit: Mapped[str | None] = mapped_column(Text)
    social_audit: Mapped[str | None] = mapped_column(Text)
    reputation_audit: Mapped[str | None] = mapped_column(Text)
    main_problems: Mapped[str | None] = mapped_column(Text)
    growth_points: Mapped[str | None] = mapped_column(Text)
    quick_improvements: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    roadmap_7_days: Mapped[str | None] = mapped_column(Text)
    roadmap_30_days: Mapped[str | None] = mapped_column(Text)
    roadmap_90_days: Mapped[str | None] = mapped_column(Text)
    next_step: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[str | None] = mapped_column(Text)
    document_path: Mapped[str | None] = mapped_column(String(500))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    notes: Mapped[list["ConsultationNote"]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["ConsultationAttachment"]] = relationship(
        back_populates="consultation",
        cascade="all, delete-orphan",
    )


class ConsultationNote(Base):
    __tablename__ = "consultation_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consultation: Mapped[Consultation] = relationship(back_populates="notes")


class ConsultationAttachment(Base):
    __tablename__ = "consultation_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consultation: Mapped[Consultation] = relationship(back_populates="attachments")

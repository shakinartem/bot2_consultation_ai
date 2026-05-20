"""create consultations

Revision ID: 0001_create_consultations
Revises:
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_create_consultations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("website_audit", sa.Text(), nullable=True),
        sa.Column("maps_audit", sa.Text(), nullable=True),
        sa.Column("social_audit", sa.Text(), nullable=True),
        sa.Column("reputation_audit", sa.Text(), nullable=True),
        sa.Column("growth_points", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.Text(), nullable=True),
        sa.Column("roadmap_7_days", sa.Text(), nullable=True),
        sa.Column("roadmap_30_days", sa.Text(), nullable=True),
        sa.Column("roadmap_90_days", sa.Text(), nullable=True),
        sa.Column("document_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consultations_company_id"), "consultations", ["company_id"], unique=False)
    op.create_table(
        "consultation_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("consultation_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consultation_notes_consultation_id"), "consultation_notes", ["consultation_id"], unique=False)
    op.create_table(
        "consultation_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("consultation_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consultation_attachments_consultation_id"), "consultation_attachments", ["consultation_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_consultation_attachments_consultation_id"), table_name="consultation_attachments")
    op.drop_table("consultation_attachments")
    op.drop_index(op.f("ix_consultation_notes_consultation_id"), table_name="consultation_notes")
    op.drop_table("consultation_notes")
    op.drop_index(op.f("ix_consultations_company_id"), table_name="consultations")
    op.drop_table("consultations")

"""add consultation context and proposal fields

Revision ID: 0003_add_consultation_context_and_proposal_fields
Revises: 0002_extend_consultation_audit_fields
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_consultation_context_and_proposal_fields"
down_revision = "0002_extend_consultation_audit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consultations", sa.Column("sales_context", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("consultation_talking_points", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("proposal_text", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("proposal_package", sa.String(length=255), nullable=True))
    op.add_column("consultations", sa.Column("proposal_budget_range", sa.String(length=255), nullable=True))
    op.add_column("consultations", sa.Column("proposal_document_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("consultations", "proposal_document_path")
    op.drop_column("consultations", "proposal_budget_range")
    op.drop_column("consultations", "proposal_package")
    op.drop_column("consultations", "proposal_text")
    op.drop_column("consultations", "consultation_talking_points")
    op.drop_column("consultations", "sales_context")

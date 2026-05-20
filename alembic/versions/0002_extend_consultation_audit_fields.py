"""extend consultation audit fields

Revision ID: 0002_extend_consultation_audit_fields
Revises: 0001_create_consultations
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_extend_consultation_audit_fields"
down_revision = "0001_create_consultations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("consultations", sa.Column("overall_conclusion", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("main_problems", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("quick_improvements", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("next_step", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("result_summary", sa.Text(), nullable=True))
    op.add_column("consultations", sa.Column("pdf_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("consultations", "pdf_path")
    op.drop_column("consultations", "result_summary")
    op.drop_column("consultations", "next_step")
    op.drop_column("consultations", "quick_improvements")
    op.drop_column("consultations", "main_problems")
    op.drop_column("consultations", "overall_conclusion")

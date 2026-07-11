"""Widen normalized role and location fields.

Revision ID: 0004_text_capacity
Revises: 0003_location_cache
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_text_capacity"
down_revision = "0003_location_cache"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "job_postings", "job_family",
        existing_type=sa.String(length=200), type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "job_postings", "metro_area",
        existing_type=sa.String(length=200), type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "salary_benchmarks", "metro_area",
        existing_type=sa.String(length=200), type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "location_cache", "metro_area",
        existing_type=sa.String(length=200), type_=sa.String(length=500),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "location_cache", "metro_area",
        existing_type=sa.String(length=500), type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.alter_column(
        "salary_benchmarks", "metro_area",
        existing_type=sa.String(length=500), type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.alter_column(
        "job_postings", "metro_area",
        existing_type=sa.String(length=500), type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.alter_column(
        "job_postings", "job_family",
        existing_type=sa.String(length=500), type_=sa.String(length=200),
        existing_nullable=True,
    )

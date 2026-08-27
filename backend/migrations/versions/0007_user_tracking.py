"""Add anonymous-device-scoped favorites, applications, notes, views, and dismissals.

Revision ID: 0007_user_tracking
Revises: 0006_source_sighting_links
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_user_tracking"
down_revision = "0006_source_sighting_links"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "job_posting_id", name="uq_job_favorites_device_job"),
    )
    op.create_index("ix_job_favorites_device_id", "job_favorites", ["device_id"])
    op.create_index("ix_job_favorites_job_posting_id", "job_favorites", ["job_posting_id"])

    op.create_table(
        "job_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="applied"),
        sa.Column("applied_date", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "job_posting_id", name="uq_job_applications_device_job"),
    )
    op.create_index("ix_job_applications_device_id", "job_applications", ["device_id"])
    op.create_index("ix_job_applications_job_posting_id", "job_applications", ["job_posting_id"])

    op.create_table(
        "job_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "job_posting_id", name="uq_job_notes_device_job"),
    )
    op.create_index("ix_job_notes_device_id", "job_notes", ["device_id"])
    op.create_index("ix_job_notes_job_posting_id", "job_notes", ["job_posting_id"])

    op.create_table(
        "job_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "job_posting_id", name="uq_job_views_device_job"),
    )
    op.create_index("ix_job_views_device_id", "job_views", ["device_id"])
    op.create_index("ix_job_views_job_posting_id", "job_views", ["job_posting_id"])
    op.create_index("ix_job_views_device_viewed", "job_views", ["device_id", "viewed_at"])

    op.create_table(
        "job_dismissals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "job_posting_id", name="uq_job_dismissals_device_job"),
    )
    op.create_index("ix_job_dismissals_device_id", "job_dismissals", ["device_id"])
    op.create_index("ix_job_dismissals_job_posting_id", "job_dismissals", ["job_posting_id"])


def downgrade():
    op.drop_table("job_dismissals")
    op.drop_table("job_views")
    op.drop_table("job_notes")
    op.drop_table("job_applications")
    op.drop_table("job_favorites")

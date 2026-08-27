"""Add anonymous-device-scoped saved searches.

Revision ID: 0008_saved_searches
Revises: 0007_user_tracking
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_saved_searches"
down_revision = "0007_user_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_id", "name", name="uq_saved_searches_device_name"),
    )
    op.create_index("ix_saved_searches_device_id", "saved_searches", ["device_id"])


def downgrade():
    op.drop_table("saved_searches")

"""Add cached location enrichment.

Revision ID: 0003_location_cache
Revises: 0002_structured_identity
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_location_cache"
down_revision = "0002_structured_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "location_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_key", sa.String(500), nullable=False),
        sa.Column("location_raw", sa.String(500), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="nominatim"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("city", sa.String(200)),
        sa.Column("state", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("metro_area", sa.String(200)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000)),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("location_key", name="uq_location_cache_key"),
    )
    op.create_index("ix_location_cache_key", "location_cache", ["location_key"])
    op.create_index("ix_location_cache_status", "location_cache", ["status"])


def downgrade():
    op.drop_index("ix_location_cache_status", table_name="location_cache")
    op.drop_index("ix_location_cache_key", table_name="location_cache")
    op.drop_table("location_cache")

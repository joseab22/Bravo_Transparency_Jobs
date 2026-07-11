"""Preserve every distinct publisher apply link.

Revision ID: 0006_source_sighting_links
Revises: 0005_source_attribution
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_source_sighting_links"
down_revision = "0005_source_attribution"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_source_sightings", sa.Column("sighting_key", sa.String(length=64), nullable=True))
    op.add_column(
        "job_source_sightings",
        sa.Column("is_direct", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE job_source_sightings "
        "SET sighting_key = md5(coalesce(source, '') || '|' || "
        "coalesce(source_url, '') || '|' || coalesce(external_id, '')) "
        "WHERE sighting_key IS NULL"
    )
    op.alter_column("job_source_sightings", "sighting_key", nullable=False)
    op.drop_constraint("uq_sightings_posting_source", "job_source_sightings", type_="unique")
    op.create_unique_constraint(
        "uq_sightings_posting_key",
        "job_source_sightings",
        ["job_posting_id", "sighting_key"],
    )
    op.create_index(
        "ix_job_source_sightings_sighting_key",
        "job_source_sightings",
        ["sighting_key"],
    )


def downgrade():
    # Multiple links from one publisher are collapsed before restoring the old
    # one-source-per-posting constraint.
    op.execute(
        "DELETE FROM job_source_sightings a USING job_source_sightings b "
        "WHERE a.id > b.id AND a.job_posting_id = b.job_posting_id "
        "AND a.source = b.source"
    )
    op.drop_index("ix_job_source_sightings_sighting_key", table_name="job_source_sightings")
    op.drop_constraint("uq_sightings_posting_key", "job_source_sightings", type_="unique")
    op.create_unique_constraint(
        "uq_sightings_posting_source",
        "job_source_sightings",
        ["job_posting_id", "source"],
    )
    op.drop_column("job_source_sightings", "is_direct")
    op.drop_column("job_source_sightings", "sighting_key")

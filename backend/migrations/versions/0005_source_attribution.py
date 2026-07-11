"""Preserve collection provider and publisher attribution.

Revision ID: 0005_source_attribution
Revises: 0004_text_capacity
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_source_attribution"
down_revision = "0004_text_capacity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_postings", sa.Column("publisher_name", sa.String(length=255), nullable=True))
    op.add_column("job_postings", sa.Column("collection_provider", sa.String(length=50), nullable=True))
    op.add_column("job_source_sightings", sa.Column("publisher_name", sa.String(length=255), nullable=True))
    op.add_column("job_source_sightings", sa.Column("collection_provider", sa.String(length=50), nullable=True))

    for table in ("job_postings", "job_snapshots", "job_events", "repost_events", "job_source_sightings"):
        op.alter_column(
            table,
            "source",
            existing_type=sa.String(length=50),
            type_=sa.String(length=100),
            existing_nullable=(table != "job_postings" and table != "job_source_sightings"),
        )

    op.execute("UPDATE job_postings SET publisher_name = source WHERE publisher_name IS NULL")
    op.execute("UPDATE job_postings SET collection_provider = source WHERE collection_provider IS NULL")
    op.execute("UPDATE job_source_sightings SET publisher_name = source WHERE publisher_name IS NULL")
    op.execute("UPDATE job_source_sightings SET collection_provider = source WHERE collection_provider IS NULL")

    op.create_index("ix_job_postings_collection_provider", "job_postings", ["collection_provider"])
    op.create_index(
        "ix_job_postings_provider_external",
        "job_postings",
        ["collection_provider", "external_id"],
    )
    op.create_index(
        "ix_job_source_sightings_collection_provider",
        "job_source_sightings",
        ["collection_provider"],
    )


def downgrade():
    op.drop_index("ix_job_source_sightings_collection_provider", table_name="job_source_sightings")
    op.drop_index("ix_job_postings_provider_external", table_name="job_postings")
    op.drop_index("ix_job_postings_collection_provider", table_name="job_postings")

    for table in ("job_source_sightings", "repost_events", "job_events", "job_snapshots", "job_postings"):
        op.alter_column(
            table,
            "source",
            existing_type=sa.String(length=100),
            type_=sa.String(length=50),
            existing_nullable=(table != "job_postings" and table != "job_source_sightings"),
        )

    op.drop_column("job_source_sightings", "collection_provider")
    op.drop_column("job_source_sightings", "publisher_name")
    op.drop_column("job_postings", "collection_provider")
    op.drop_column("job_postings", "publisher_name")

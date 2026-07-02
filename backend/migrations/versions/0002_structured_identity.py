"""Add structured title identity and active hiring confidence.

Revision ID: 0002_structured_identity
Revises: 0001_initial
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_structured_identity"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_postings", sa.Column("identity_fingerprint", sa.String(64), nullable=True))
    op.add_column("job_postings", sa.Column("canonical_job_id", sa.Integer(), nullable=True))
    op.add_column(
        "job_postings",
        sa.Column("listing_classification", sa.String(30), nullable=False, server_default="original"),
    )
    op.add_column("job_postings", sa.Column("job_family", sa.String(200), nullable=True))
    op.add_column("job_postings", sa.Column("specialization", sa.String(300), nullable=True))
    op.add_column("job_postings", sa.Column("title_parse_confidence", sa.Float(), nullable=True))
    op.add_column("job_postings", sa.Column("active_hiring_confidence", sa.Float(), nullable=True))

    op.create_foreign_key(
        "fk_job_postings_canonical_job_id",
        "job_postings",
        "job_postings",
        ["canonical_job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Existing records receive safe defaults. New ingestion recomputes the
    # stronger SHA-256 fingerprint from structured title fields.
    op.execute("UPDATE job_postings SET job_family = title_normalized WHERE job_family IS NULL")
    op.execute(
        "UPDATE job_postings "
        "SET identity_fingerprint = md5(job_identity_key) "
        "WHERE identity_fingerprint IS NULL"
    )
    op.execute("UPDATE job_postings SET canonical_job_id = id WHERE canonical_job_id IS NULL")
    op.execute(
        "UPDATE job_postings SET title_parse_confidence = 0.50 "
        "WHERE title_parse_confidence IS NULL"
    )

    op.create_index("ix_job_postings_identity_fingerprint", "job_postings", ["identity_fingerprint"])
    op.create_index("ix_job_postings_canonical_job_id", "job_postings", ["canonical_job_id"])
    op.create_index("ix_job_postings_listing_classification", "job_postings", ["listing_classification"])
    op.create_index("ix_job_postings_job_family", "job_postings", ["job_family"])
    op.create_index(
        "ix_job_postings_fingerprint_active",
        "job_postings",
        ["identity_fingerprint", "is_active"],
    )


def downgrade():
    op.drop_index("ix_job_postings_fingerprint_active", table_name="job_postings")
    op.drop_index("ix_job_postings_job_family", table_name="job_postings")
    op.drop_index("ix_job_postings_listing_classification", table_name="job_postings")
    op.drop_index("ix_job_postings_canonical_job_id", table_name="job_postings")
    op.drop_index("ix_job_postings_identity_fingerprint", table_name="job_postings")
    op.drop_constraint("fk_job_postings_canonical_job_id", "job_postings", type_="foreignkey")

    op.drop_column("job_postings", "active_hiring_confidence")
    op.drop_column("job_postings", "title_parse_confidence")
    op.drop_column("job_postings", "specialization")
    op.drop_column("job_postings", "job_family")
    op.drop_column("job_postings", "listing_classification")
    op.drop_column("job_postings", "canonical_job_id")
    op.drop_column("job_postings", "identity_fingerprint")

"""Initial schema — all tables

Revision ID: 0001_initial
Revises: —
Create Date: 2025-06-01
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # companies
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_normalized", sa.String(255), nullable=False, unique=True),
        sa.Column("industry", sa.String(100)),
        sa.Column("employee_count", sa.Integer),
        sa.Column("glassdoor_rating", sa.Float),
        sa.Column("glassdoor_url", sa.String(500)),
        sa.Column("website", sa.String(500)),
        sa.Column("linkedin_url", sa.String(500)),
        sa.Column("turnover_score", sa.Float),
        sa.Column("hiring_intensity", sa.Float),
        sa.Column("ghost_job_rate", sa.Float),
        sa.Column("avg_reposts", sa.Float),
        sa.Column("median_time_to_fill", sa.Integer),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_companies_name_normalized", "companies", ["name_normalized"])

    # job_postings
    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("job_identity_key", sa.String(500), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("title_raw", sa.String(500), nullable=False),
        sa.Column("title_normalized", sa.String(500), nullable=False),
        sa.Column("location_raw", sa.String(500)),
        sa.Column("city", sa.String(200)),
        sa.Column("state", sa.String(100)),
        sa.Column("country", sa.String(100), server_default="US"),
        sa.Column("metro_area", sa.String(200)),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("remote_type", sa.String(50)),
        sa.Column("seniority", sa.String(50)),
        sa.Column("employment_type", sa.String(50)),
        sa.Column("department", sa.String(200)),
        sa.Column("industry", sa.String(200)),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("salary_currency", sa.String(10), server_default="USD"),
        sa.Column("salary_listed", sa.Boolean, server_default="false"),
        sa.Column("education_required", sa.String(200)),
        sa.Column("experience_years_min", sa.Integer),
        sa.Column("experience_years_max", sa.Integer),
        sa.Column("description_raw", sa.Text),
        sa.Column("date_posted", sa.DateTime),
        sa.Column("date_first_seen", sa.DateTime, server_default=sa.func.now()),
        sa.Column("date_last_seen", sa.DateTime, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("days_active", sa.Integer, server_default="0"),
        sa.Column("applicant_count", sa.Integer),
        # Transparency scores
        sa.Column("ghost_job_probability", sa.Float),
        sa.Column("ghost_confidence", sa.Float),
        sa.Column("health_score", sa.Float),
        sa.Column("competition_score", sa.Float),
        sa.Column("interview_opportunity_score", sa.Float),
        sa.Column("salary_fairness_score", sa.Float),
        sa.Column("market_salary", sa.Integer),
        sa.Column("stability_score", sa.Float),
        # Analytics fields
        sa.Column("activity_score", sa.Float),
        sa.Column("description_change_score", sa.Float),
        sa.Column("applicant_trend", sa.Float),
        sa.Column("salary_trend", sa.Float),
        sa.Column("repost_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_job_postings_identity_key", "job_postings", ["job_identity_key"])
    op.create_index("ix_job_postings_title_normalized", "job_postings", ["title_normalized"])
    op.create_index("ix_job_postings_metro_area", "job_postings", ["metro_area"])
    op.create_index("ix_job_postings_is_active", "job_postings", ["is_active"])
    op.create_index("ix_job_postings_date_first_seen", "job_postings", ["date_first_seen"])
    op.create_index("ix_job_postings_source_external", "job_postings", ["source", "external_id"])

    # job_snapshots (spec: snapshot_id, job_id, source, applicants, description, salary, date_seen)
    op.create_table(
        "job_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_posting_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("snapshot_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("source", sa.String(50)),
        sa.Column("applicant_count", sa.Integer),
        sa.Column("description_raw", sa.Text),
        sa.Column("description_hash", sa.String(64)),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("title_raw", sa.String(500)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )
    op.create_index("ix_job_snapshots_job_id", "job_snapshots", ["job_posting_id"])
    op.create_index("ix_job_snapshots_at", "job_snapshots", ["snapshot_at"])

    # job_events (spec: event_id, job_id, event_type, timestamp)
    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_posting_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
        sa.Column("source", sa.String(50)),
        sa.Column("payload", sa.JSON),
        sa.Column("description", sa.String(500)),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_posting_id"])
    op.create_index("ix_job_events_timestamp", "job_events", ["timestamp"])
    op.create_index("ix_job_events_type", "job_events", ["event_type"])

    # job_embeddings (spec: embedding_id, job_id, vector)
    op.create_table(
        "job_embeddings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_posting_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False, unique=True),
        sa.Column("vector", Vector(384), nullable=False),
        sa.Column("model_name", sa.String(200), server_default="all-MiniLM-L6-v2"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    # IVFFlat index for approximate nearest-neighbor search
    op.execute(
        "CREATE INDEX ix_job_embeddings_vector ON job_embeddings "
        "USING ivfflat (vector vector_cosine_ops) WITH (lists = 100)"
    )

    # job_skills
    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_posting_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("skill", sa.String(200), nullable=False),
        sa.Column("skill_normalized", sa.String(200), nullable=False),
        sa.Column("skill_category", sa.String(100)),
        sa.UniqueConstraint("job_posting_id", "skill_normalized", name="uq_job_skills"),
    )
    op.create_index("ix_job_skills_normalized", "job_skills", ["skill_normalized"])

    # repost_events
    op.create_table(
        "repost_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_posting_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("job_identity_key", sa.String(500), nullable=False),
        sa.Column("occurrence_number", sa.Integer, nullable=False),
        sa.Column("date_seen", sa.DateTime, nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("days_since_previous", sa.Integer),
    )
    op.create_index("ix_repost_events_identity_key", "repost_events", ["job_identity_key"])
    op.create_index("ix_repost_events_date", "repost_events", ["date_seen"])

    # job_source_sightings
    op.create_table(
        "job_source_sightings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("job_posting_id", sa.Integer, sa.ForeignKey("job_postings.id"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("external_id", sa.String(255)),
        sa.Column("first_seen", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime, server_default=sa.func.now()),
        sa.Column("applicant_count", sa.Integer),
        sa.UniqueConstraint("job_posting_id", "source", name="uq_sightings_posting_source"),
    )
    op.create_index("ix_source_sightings_job_id", "job_source_sightings", ["job_posting_id"])

    # salary_benchmarks
    op.create_table(
        "salary_benchmarks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title_normalized", sa.String(500), nullable=False),
        sa.Column("metro_area", sa.String(200)),
        sa.Column("seniority", sa.String(50)),
        sa.Column("salary_p25", sa.Integer),
        sa.Column("salary_p50", sa.Integer, nullable=False),
        sa.Column("salary_p75", sa.Integer),
        sa.Column("sample_size", sa.Integer, server_default="0"),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("title_normalized", "metro_area", "seniority", name="uq_salary_benchmark"),
    )
    op.create_index("ix_salary_benchmarks_title", "salary_benchmarks", ["title_normalized"])


def downgrade():
    op.drop_table("salary_benchmarks")
    op.drop_table("job_source_sightings")
    op.drop_table("repost_events")
    op.drop_table("job_skills")
    op.execute("DROP INDEX IF EXISTS ix_job_embeddings_vector")
    op.drop_table("job_embeddings")
    op.drop_table("job_events")
    op.drop_table("job_snapshots")
    op.drop_table("job_postings")
    op.drop_table("companies")

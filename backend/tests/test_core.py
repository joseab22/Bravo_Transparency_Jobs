from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import configure_mappers

from app.core.config import KNOWN_SOURCES, Settings
from app.models.models import Base, JobPosting, LocationCache
from app.services.normalizer import (
    annualize_salary,
    build_identity_fingerprint,
    build_job_identity_key,
    calculate_days_active,
    decompose_title,
    extract_seniority,
    extract_skills,
    infer_location_components,
    normalize_company_name,
    normalize_employment_type,
    normalize_location_text,
    normalize_remote_type,
    normalize_title,
    prepare_job_record,
)
from app.services.repost_detector import RepostDetectionService
from app.workers.scrapers import SCRAPER_REGISTRY
from app.workers.scrapers.simplify import SimplifyScraper


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SWE II", "software engineer"),
        ("SDE", "software engineer"),
        ("Business Intelligence Analyst", "data analyst"),
        ("ML Engineer", "machine learning engineer"),
        ("Site Reliability Engineer", "site reliability engineer"),
        ("Senior Backend Engineer", "software engineer"),
    ],
)
def test_title_family_normalization(raw, expected):
    assert normalize_title(raw) == expected


def test_decompose_title_preserves_specialization():
    admin = decompose_title("Senior Software Engineer - Admin")
    lead = decompose_title("Senior Software Engineer - Lead")
    assert admin["job_family"] == lead["job_family"] == "software engineer"
    assert admin["seniority"] == lead["seniority"] == "Senior"
    assert admin["specialization"] == "admin"
    assert lead["specialization"] == "tech_lead"


def test_unknown_title_is_not_forced_into_wrong_family():
    result = decompose_title("Developer Experience Evangelist")
    assert result["job_family"] is None
    assert result["title_normalized"]
    assert result["confidence"] < 0.8


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Sr. Engineer", "Senior"), ("Principal Engineer", "Lead"), ("Intern", "Entry"), ("Data Analyst", "Mid")],
)
def test_seniority(raw, expected):
    assert extract_seniority(raw) == expected


def test_company_normalization():
    assert normalize_company_name("Acme Technologies, Inc.") == "acme technologies"


def test_identity_fingerprint_is_location_independent():
    first = build_identity_fingerprint("Acme", "software engineer", "backend", "Senior", "Full-time", "Remote")
    second = build_identity_fingerprint("Acme", "software engineer", "backend", "Senior", "Full-time", "Remote")
    assert first == second and len(first) == 64


def test_identity_key_contains_location_bucket_but_stable_fingerprint():
    first = build_job_identity_key("Acme", "software engineer", "New York, NY", specialization="backend", seniority="Senior", employment_type="Full-time", remote_type="Onsite")
    second = build_job_identity_key("Acme", "software engineer", "Austin, TX", specialization="backend", seniority="Senior", employment_type="Full-time", remote_type="Onsite")
    assert first != second
    assert "acme" in first


def test_remote_locations_share_bucket():
    first = build_job_identity_key("Acme", "software engineer", "California", remote_type="Remote")
    second = build_job_identity_key("Acme", "software engineer", "New York", remote_type="Remote")
    assert first == second


def test_location_normalization_has_no_network_dependency():
    assert normalize_location_text("San Francisco, California") == "San Francisco, CA"
    assert infer_location_components("Remote")["metro_area"] == "Remote"


def test_work_arrangement_and_employment_normalization():
    assert normalize_remote_type(None, "Remote - US") == "Remote"
    assert normalize_remote_type("Hybrid", "Boston") == "Hybrid"
    assert normalize_employment_type(None, "Software Engineering Intern") == "Internship"


def test_salary_annualization():
    assert annualize_salary(50, 60, "hour") == (104000, 124800)
    assert annualize_salary("$100,000", "$120,000", "year") == (100000, 120000)


def test_skill_extraction():
    names = {item["skill"] for item in extract_skills("Python, SQL, AWS, Docker and Kubernetes")}
    assert {"Python", "SQL", "AWS", "Docker", "Kubernetes"} <= names


def test_days_active_uses_oldest_valid_observation():
    now = datetime(2026, 7, 5)
    assert calculate_days_active(datetime(2026, 7, 1), datetime(2026, 7, 3), now) == 4


def test_prepare_job_record_centralizes_source_normalization():
    record = prepare_job_record({
        "source": "SIMPLIFY",
        "company_name": "Acme Inc.",
        "title_raw": "Senior Backend Software Engineer",
        "location_raw": "Remote - US",
        "description_raw": "Python and AWS",
    })
    assert record["source"] == "simplify"
    assert record["job_family"] == "software engineer"
    assert record["remote_type"] == "Remote"
    assert record["identity_fingerprint"]
    assert record["skills"]


def fake_job(**overrides):
    now = datetime(2026, 7, 5)
    values = dict(
        id=1,
        company_id=1,
        title_normalized="software engineer",
        job_family="software engineer",
        specialization=None,
        seniority="Senior",
        employment_type="Full-time",
        remote_type="Remote",
        metro_area="Remote",
        location_raw="Remote",
        latitude=None,
        longitude=None,
        embedding=None,
        date_posted=now,
        date_first_seen=now,
        date_last_seen=now,
        created_at=now,
        is_active=True,
        canonical_job_id=None,
        repost_count=0,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_different_specializations_do_not_merge():
    service = RepostDetectionService()
    assert not service.roles_match(fake_job(specialization="admin"), fake_job(id=2, specialization="tech_lead"))


def test_remote_and_onsite_do_not_merge():
    service = RepostDetectionService()
    assert not service.roles_match(fake_job(remote_type="Remote"), fake_job(id=2, remote_type="Onsite"))


def test_simultaneous_remote_regions_are_parallel():
    service = RepostDetectionService()
    first = fake_job(location_raw="California", metro_area="California")
    second = fake_job(id=2, location_raw="New York", metro_area="New York", date_posted=first.date_posted + timedelta(hours=4))
    assert service.classify_pair(second, first) == "parallel"


def test_closed_role_after_gap_is_repost():
    service = RepostDetectionService()
    first = fake_job(is_active=False, date_last_seen=datetime(2026, 6, 1), date_first_seen=datetime(2026, 5, 1), date_posted=datetime(2026, 5, 1))
    second = fake_job(id=2, date_first_seen=datetime(2026, 6, 20), date_posted=datetime(2026, 6, 20))
    assert service.classify_pair(second, first) == "repost"


def test_closed_role_in_different_onsite_metro_is_not_repost():
    service = RepostDetectionService()
    first = fake_job(remote_type="Onsite", metro_area="New York, NY", location_raw="New York, NY", is_active=False, date_last_seen=datetime(2026, 6, 1), date_first_seen=datetime(2026, 5, 1), date_posted=datetime(2026, 5, 1))
    second = fake_job(id=2, remote_type="Onsite", metro_area="Austin, TX", location_raw="Austin, TX", date_first_seen=datetime(2026, 6, 20), date_posted=datetime(2026, 6, 20))
    assert service.classify_pair(second, first) == "original"


def test_orm_matches_migrations():
    configure_mappers()
    assert len(Base.metadata.tables) == 10
    for name in ("identity_fingerprint", "canonical_job_id", "listing_classification", "job_family", "active_hiring_confidence"):
        assert name in JobPosting.__table__.columns
    assert len(LocationCache.__table__.columns) == 16


def test_registry_covers_known_sources():
    assert set(SCRAPER_REGISTRY) == KNOWN_SOURCES


def test_default_schedule_enables_only_simplify():
    settings = Settings(_env_file=None)
    assert settings.enabled_source_set == {"simplify"}


def test_scrapers_do_not_call_geocoder_in_parsers():
    scraper_dir = Path(__file__).parents[1] / "app" / "workers" / "scrapers"
    for path in scraper_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        assert "geocode_location(" not in path.read_text(), path.name


def test_simplify_parser_handles_multiple_locations_without_geocoding():
    job = SimplifyScraper().parse_job({
        "id": "abc",
        "title": "Software Engineer Intern",
        "company_name": "Acme",
        "locations": ["Remote", "San Francisco, CA"],
        "url": "https://example.test/job",
        "description": "Python",
        "date_posted": "2026-07-01",
    })
    assert job is not None
    assert job["location_raw"] == "Remote | San Francisco, CA"
    assert job["employment_type"] == "Internship"
    assert "latitude" not in job


def test_scoring_weights_validate():
    with pytest.raises(ValueError):
        Settings(_env_file=None, ghost_job_repost_weight=0.9)

@pytest.mark.asyncio
async def test_ingestion_preserves_parallel_stable_ids(tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.db.base import Base
    from app.models.models import JobPosting
    from app.workers.ingestion import ingest_jobs

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ingest.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    jobs = [
        {"source": "simplify", "external_id": "req-1", "source_url": "https://example/1", "company_name": "Acme", "title_raw": "Senior Backend Software Engineer", "location_raw": "Remote - CA"},
        {"source": "simplify", "external_id": "req-2", "source_url": "https://example/2", "company_name": "Acme", "title_raw": "Senior Backend Software Engineer", "location_raw": "Remote - NY"},
    ]
    async with Session() as db:
        result = await ingest_jobs(jobs, db)
        count = await db.scalar(select(func.count(JobPosting.id)))
    await engine.dispose()
    assert result == {"total": 2, "created": 2, "updated": 0, "errors": 0}
    assert count == 2

@pytest.mark.asyncio
async def test_ingestion_updates_prefetched_stable_ids_without_duplication(tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.db.base import Base
    from app.models.models import JobPosting
    from app.workers.ingestion import ingest_jobs

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'repeat.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    original = {
        "source": "simplify",
        "external_id": "req-1",
        "source_url": "https://example/1",
        "company_name": "Acme",
        "title_raw": "Senior Backend Software Engineer",
        "location_raw": "Remote - CA",
        "applicant_count": 10,
    }
    updated = dict(original, applicant_count=25)
    async with Session() as db:
        first = await ingest_jobs([original], db)
        second = await ingest_jobs([updated], db)
        count = await db.scalar(select(func.count(JobPosting.id)))
        job = (await db.execute(select(JobPosting))).scalar_one()
    await engine.dispose()

    assert first["created"] == 1
    assert second == {"total": 1, "created": 0, "updated": 1, "errors": 0}
    assert count == 1
    assert job.applicant_count == 25


def test_title_similarity_is_model_free_by_default(monkeypatch):
    from app.core.config import settings
    from app.services import repost_detector

    monkeypatch.setattr(settings, "semantic_title_matching_enabled", False)

    def fail_if_loaded():
        raise AssertionError("embedding model should not load")

    monkeypatch.setattr(repost_detector, "get_embedding_model", fail_if_loaded)
    score = repost_detector.title_similarity("backend software engineer", "software engineer backend")
    assert 0 < score < 1

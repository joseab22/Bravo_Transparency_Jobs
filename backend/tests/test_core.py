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
    normalize_metro_area,
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


def test_multi_location_uses_stable_database_safe_bucket():
    raw = " | ".join(f"City {index}, CA" for index in range(80))
    record = prepare_job_record({
        "source": "simplify",
        "company_name": "Acme",
        "title_raw": "Software Developer",
        "location_raw": raw,
    })
    assert len(record["location_raw"]) == 500
    assert record["metro_area"] == "Multiple locations"
    assert normalize_metro_area(raw) == "Multiple locations"


def test_role_and_metro_columns_match_normalizer_capacity():
    assert JobPosting.__table__.c.job_family.type.length == 500
    assert JobPosting.__table__.c.metro_area.type.length == 500
    assert LocationCache.__table__.c.metro_area.type.length == 500


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
    from sqlalchemy.orm import selectinload
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


def test_jsearch_preserves_actual_publishers_and_apply_options():
    from app.workers.scrapers.jsearch import extract_source_options, select_primary_source

    raw = {
        "job_id": "job-123",
        "job_publisher": "Acme Careers",
        "job_apply_link": "https://careers.acme.test/jobs/123",
        "apply_options": [
            {"publisher": "LinkedIn", "apply_link": "https://linkedin.com/jobs/view/123"},
            {"publisher": "Indeed", "apply_link": "https://indeed.com/viewjob?jk=123"},
            {"publisher": "ZipRecruiter", "apply_link": "https://ziprecruiter.com/jobs/123"},
        ],
    }
    options = extract_source_options(raw)
    assert {item["source"] for item in options} == {
        "acme-careers", "linkedin", "indeed", "ziprecruiter"
    }
    primary, _ = select_primary_source(raw, expected_source="linkedin")
    assert primary["source"] == "linkedin"
    assert all(item["collection_provider"] == "jsearch" for item in options)


def test_linkedin_jsearch_parser_uses_publisher_attribution():
    from app.workers.scrapers.linkedin import LinkedInScraper

    parsed = LinkedInScraper(max_pages=1).parse_job({
        "job_id": "abc",
        "job_title": "Data Analyst",
        "employer_name": "Acme",
        "job_city": "Los Angeles",
        "job_state": "CA",
        "job_publisher": "LinkedIn",
        "job_apply_link": "https://linkedin.com/jobs/view/abc",
        "apply_options": [
            {"publisher": "LinkedIn", "apply_link": "https://linkedin.com/jobs/view/abc"},
            {"publisher": "Indeed", "apply_link": "https://indeed.com/viewjob?jk=abc"},
        ],
    })
    assert parsed is not None
    assert parsed["source"] == "linkedin"
    assert parsed["collection_provider"] == "jsearch"
    assert {item["source"] for item in parsed["source_options"]} == {"linkedin", "indeed"}


@pytest.mark.asyncio
async def test_ingestion_merges_same_jsearch_id_and_retains_all_publishers(tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload
    from app.db.base import Base
    from app.models.models import JobPosting, JobSourceSighting
    from app.services.source_attribution import load_canonical_sources
    from app.workers.ingestion import ingest_jobs

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jsearch.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    common = {
        "collection_provider": "jsearch",
        "external_id": "shared-job-id",
        "company_name": "Acme",
        "title_raw": "Data Analyst",
        "location_raw": "Los Angeles, CA",
    }
    jobs = [
        {
            **common,
            "source": "linkedin",
            "publisher_name": "LinkedIn",
            "source_url": "https://linkedin.com/jobs/view/shared-job-id",
            "source_options": [{
                "source": "linkedin",
                "publisher_name": "LinkedIn",
                "collection_provider": "jsearch",
                "source_url": "https://linkedin.com/jobs/view/shared-job-id",
                "external_id": "shared-job-id",
            }],
        },
        {
            **common,
            "source": "indeed",
            "publisher_name": "Indeed",
            "source_url": "https://indeed.com/viewjob?jk=shared-job-id",
            "source_options": [{
                "source": "indeed",
                "publisher_name": "Indeed",
                "collection_provider": "jsearch",
                "source_url": "https://indeed.com/viewjob?jk=shared-job-id",
                "external_id": "shared-job-id",
            }],
        },
    ]

    async with Session() as db:
        result = await ingest_jobs(jobs, db)
        posting_count = await db.scalar(select(func.count(JobPosting.id)))
        sighting_count = await db.scalar(select(func.count(JobSourceSighting.id)))
        posting = (await db.execute(
            select(JobPosting).options(selectinload(JobPosting.source_sightings))
        )).scalar_one()
        sources = await load_canonical_sources([posting], db)

    await engine.dispose()
    assert result == {"total": 2, "created": 1, "updated": 1, "errors": 0}
    assert posting_count == 1
    assert sighting_count == 2
    assert {item["source"] for item in sources[posting.id]} == {"linkedin", "indeed"}

@pytest.mark.asyncio
async def test_source_attribution_falls_back_for_legacy_rows(tmp_path):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.db.base import Base
    from app.models.models import Company, JobPosting
    from app.services.source_attribution import load_canonical_sources

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy-source.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        company = Company(name="Acme", name_normalized="acme")
        db.add(company)
        await db.flush()
        job = JobPosting(
            company_id=company.id,
            job_identity_key="acme|data analyst|remote",
            source="simplify",
            publisher_name="Simplify",
            collection_provider="simplify",
            source_url="https://simplify.jobs/p/legacy",
            external_id="legacy",
            title_raw="Data Analyst",
            title_normalized="data analyst",
            location_raw="Remote",
            country="US",
        )
        db.add(job)
        await db.flush()
        job.canonical_job_id = job.id
        await db.commit()
        sources = await load_canonical_sources([job], db)

    await engine.dispose()
    assert sources[job.id][0]["source"] == "simplify"
    assert sources[job.id][0]["source_url"] == "https://simplify.jobs/p/legacy"


def test_generic_jsearch_parser_attributes_returned_publisher():
    from app.workers.scrapers.jsearch import JSearchScraper

    parsed = JSearchScraper(max_pages=1).parse_job({
        "job_id": "zip-123",
        "job_title": "Software Engineer",
        "employer_name": "Acme",
        "job_city": "San Diego",
        "job_state": "CA",
        "job_publisher": "ZipRecruiter",
        "job_apply_link": "https://ziprecruiter.com/jobs/zip-123",
        "apply_options": [
            {"publisher": "ZipRecruiter", "apply_link": "https://ziprecruiter.com/jobs/zip-123"},
            {"publisher": "Acme Careers", "apply_link": "https://careers.acme.test/zip-123"},
        ],
    })
    assert parsed is not None
    assert parsed["source"] == "ziprecruiter"
    assert parsed["collection_provider"] == "jsearch"
    assert {item["source"] for item in parsed["source_options"]} == {
        "ziprecruiter", "company_site"
    }



def test_jsearch_pro_schedule_stays_inside_protected_budget():
    configured = Settings(
        _env_file=None,
        enabled_scraper_sources="simplify,jsearch",
        jsearch_pages_per_query=10,
        jsearch_schedule_every_hours=24,
        jsearch_monthly_request_limit=10_000,
        jsearch_request_reserve=1_000,
    )
    assert configured.jsearch_requests_per_run == 70
    assert configured.jsearch_estimated_monthly_requests == 2_170
    assert configured.jsearch_application_budget == 9_000


def test_jsearch_prevents_duplicate_targeted_schedules_by_default():
    with pytest.raises(ValueError, match="generic jsearch OR"):
        Settings(
            _env_file=None,
            enabled_scraper_sources="simplify,jsearch,linkedin",
        )


def test_jsearch_rejects_schedule_that_can_exceed_protected_budget():
    with pytest.raises(ValueError, match="exceeds the protected application budget"):
        Settings(
            _env_file=None,
            enabled_scraper_sources="simplify,jsearch",
            jsearch_pages_per_query=20,
            jsearch_schedule_every_hours=3,
            jsearch_monthly_request_limit=10_000,
            jsearch_request_reserve=1_000,
        )


def test_jsearch_excludes_simplify_but_keeps_other_publishers():
    from app.workers.scrapers.jsearch import JSearchScraper

    parser = JSearchScraper(max_pages=1)
    mixed = parser.parse_job({
        "job_id": "mixed-1",
        "job_title": "Data Engineer",
        "employer_name": "Acme",
        "job_location": "Remote",
        "job_publisher": "Simplify Jobs",
        "job_apply_link": "https://simplify.jobs/p/mixed-1",
        "apply_options": [
            {"publisher": "Simplify", "apply_link": "https://simplify.jobs/p/mixed-1"},
            {"publisher": "LinkedIn", "apply_link": "https://linkedin.com/jobs/view/mixed-1"},
            {"publisher": "Indeed", "apply_link": "https://indeed.com/viewjob?jk=mixed-1"},
        ],
    })
    assert mixed is not None
    assert mixed["source"] == "linkedin"
    assert {item["source"] for item in mixed["source_options"]} == {"linkedin", "indeed"}
    assert "-site:simplify.jobs" in parser._search_query("data engineer")

    excluded = parser.parse_job({
        "job_id": "simplify-only",
        "job_title": "Data Engineer",
        "employer_name": "Acme",
        "job_location": "Remote",
        "job_publisher": "Simplify",
        "job_apply_link": "https://simplify.jobs/p/simplify-only",
    })
    assert excluded is None


def test_jsearch_extracts_structured_fields_and_all_apply_links():
    from app.workers.scrapers.jsearch import JSearchScraper

    parsed = JSearchScraper(max_pages=1).parse_job({
        "job_id": "structured-1",
        "job_title": "Senior Data Analyst",
        "employer_name": "Acme",
        "employer_website": "https://www.acme.test",
        "employer_company_type": "Technology",
        "job_city": "Los Angeles",
        "job_state": "CA",
        "job_country": "US",
        "job_location": "Los Angeles, CA",
        "job_latitude": 34.0522,
        "job_longitude": -118.2437,
        "job_is_remote": False,
        "job_publisher": "Indeed",
        "job_apply_link": "https://indeed.com/viewjob?jk=structured-1&utm_source=test",
        "job_apply_is_direct": False,
        "apply_options": [
            {"publisher": "Indeed", "apply_link": "https://indeed.com/viewjob?jk=structured-1&utm_medium=x"},
            {"publisher": "Indeed", "apply_link": "https://indeed.com/viewjob?jk=structured-1&from=search"},
            {"publisher": "Acme Careers", "apply_link": "https://careers.acme.test/jobs/structured-1", "is_direct": True},
        ],
        "job_min_salary": 50,
        "job_max_salary": 60,
        "job_salary_period": "hour",
        "job_salary_currency": "USD",
        "job_employment_type_text": "FULLTIME",
        "job_required_experience": {"required_experience_in_months": 36},
        "job_required_education": {"bachelors_degree": True},
        "job_occupational_categories": ["Data & Analytics", "Business Intelligence"],
        "job_description": "Build dashboards with Python, SQL, and Tableau.",
        "job_posted_at_datetime_utc": "2026-07-05T10:30:00Z",
    })
    assert parsed is not None
    assert parsed["source"] == "indeed"
    assert parsed["company_website"] == "https://www.acme.test"
    assert parsed["latitude"] == pytest.approx(34.0522)
    assert parsed["longitude"] == pytest.approx(-118.2437)
    assert parsed["salary_min"] == 104_000
    assert parsed["salary_max"] == 124_800
    assert parsed["education_required"] == "Bachelor's degree"
    assert (parsed["experience_years_min"], parsed["experience_years_max"]) == (3, 3)
    assert parsed["department"] == "Data & Analytics, Business Intelligence"
    assert parsed["industry"] == "Technology"
    assert parsed["date_posted"].year == 2026
    # Tracking-only URL differences collapse into one board link.
    assert len(parsed["source_options"]) == 2
    assert [item["source"] for item in parsed["source_options"]].count("indeed") == 1
    assert any(item["source"] == "company_site" and item["is_direct"] for item in parsed["source_options"])


@pytest.mark.asyncio
async def test_ingestion_retains_multiple_links_from_same_publisher(tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload
    from app.db.base import Base
    from app.models.models import JobPosting, JobSourceSighting
    from app.services.source_attribution import load_canonical_sources
    from app.workers.ingestion import ingest_jobs

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'multi-link.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    job = {
        "source": "indeed",
        "publisher_name": "Indeed",
        "collection_provider": "jsearch",
        "external_id": "same-board-two-links",
        "source_url": "https://indeed.com/viewjob?jk=one",
        "company_name": "Acme",
        "title_raw": "Data Analyst",
        "location_raw": "Remote",
        "source_options": [
            {
                "source": "indeed",
                "publisher_name": "Indeed",
                "collection_provider": "jsearch",
                "source_url": "https://indeed.com/viewjob?jk=one",
                "external_id": "same-board-two-links",
            },
            {
                "source": "indeed",
                "publisher_name": "Indeed",
                "collection_provider": "jsearch",
                "source_url": "https://indeed.com/viewjob?jk=two",
                "external_id": "same-board-two-links",
            },
        ],
    }

    async with Session() as db:
        result = await ingest_jobs([job], db)
        posting = (await db.execute(
            select(JobPosting).options(selectinload(JobPosting.source_sightings))
        )).scalar_one()
        count = await db.scalar(select(func.count(JobSourceSighting.id)))
        sources = await load_canonical_sources([posting], db)

    await engine.dispose()
    assert result["errors"] == 0
    assert count == 2
    assert len(sources[posting.id]) == 2
    assert {item["source_url"] for item in sources[posting.id]} == {
        "https://indeed.com/viewjob?jk=one",
        "https://indeed.com/viewjob?jk=two",
    }



@pytest.mark.asyncio
async def test_jsearch_uses_cursor_search_v2_for_multiple_pages(monkeypatch):
    from app.core.config import settings
    from app.workers.scrapers.jsearch import JSearchScraper

    monkeypatch.setattr(settings, "openwebninja_api_key", "test-only")
    scraper = JSearchScraper(max_pages=2)
    calls = []

    async def fake_request(url, **kwargs):
        calls.append((url, kwargs["params"]))
        if len(calls) == 1:
            return {"data": [{"job_id": "one"}], "cursor": "next-page-token"}
        return {"data": [{"job_id": "two"}]}

    monkeypatch.setattr(scraper, "request_json", fake_request)
    first = await scraper.fetch_jobs("data analyst", 1)
    second = await scraper.fetch_jobs("data analyst", 2)

    assert first["data"][0]["job_id"] == "one"
    assert second["data"][0]["job_id"] == "two"
    assert all(url.endswith("/search-v2") for url, _ in calls)
    assert "cursor" not in calls[0][1]
    assert calls[1][1]["cursor"] == "next-page-token"


@pytest.mark.asyncio
async def test_request_budget_stops_before_configured_monthly_limit():
    from app.services.request_budget import RapidAPIRequestBudget, RequestBudgetExceeded

    class FakeRedis:
        def __init__(self):
            self.data = {}

        async def eval(self, _script, _key_count, _key, _now, application_budget, reserve, _ttl):
            provider_remaining = self.data.get("provider_remaining")
            if provider_remaining is not None and int(provider_remaining) <= int(reserve):
                return -2
            used = int(self.data.get("local_used", 0)) + 1
            if used > int(application_budget):
                return -1
            self.data["local_used"] = used
            if provider_remaining is not None:
                self.data["provider_remaining"] = int(provider_remaining) - 1
            return used

        async def hset(self, _key, mapping):
            self.data.update(mapping)

        async def expire(self, *_args):
            return True

        async def hgetall(self, _key):
            return {key: str(value) for key, value in self.data.items()}

        async def delete(self, _key):
            self.data.clear()

        async def aclose(self):
            return None

    budget = RapidAPIRequestBudget(
        "redis://unused",
        namespace="jsearch-test",
        monthly_limit=5,
        reserve=2,
    )
    fake = FakeRedis()
    budget._redis = fake

    assert await budget.reserve_request() == 1
    assert await budget.reserve_request() == 2
    assert await budget.reserve_request() == 3
    with pytest.raises(RequestBudgetExceeded, match="application budget reached"):
        await budget.reserve_request()

    fake.data = {"provider_remaining": 2, "local_used": 0}
    with pytest.raises(RequestBudgetExceeded, match="provider-reported remaining"):
        await budget.reserve_request()


@pytest.mark.asyncio
async def test_ingestion_reconciles_legacy_sighting_key_without_duplication(tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload
    from app.db.base import Base
    from app.models.models import Company, JobPosting, JobSourceSighting
    from app.services.normalizer import build_source_sighting_key
    from app.workers.ingestion import ingest_jobs

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy-key.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        company = Company(name="Acme", name_normalized="acme")
        db.add(company)
        await db.flush()
        posting = JobPosting(
            company_id=company.id,
            job_identity_key="acme|data analyst|remote",
            identity_fingerprint="f" * 64,
            source="indeed",
            publisher_name="Indeed",
            collection_provider="jsearch",
            external_id="legacy-id",
            source_url="https://indeed.com/viewjob?jk=legacy-id",
            title_raw="Data Analyst",
            title_normalized="data analyst",
            location_raw="Remote",
            country="US",
        )
        db.add(posting)
        await db.flush()
        db.add(JobSourceSighting(
            job_posting_id=posting.id,
            sighting_key="legacy-md5-key",
            source="indeed",
            publisher_name="Indeed",
            collection_provider="jsearch",
            source_url="https://indeed.com/viewjob?jk=legacy-id&utm_source=old",
            external_id="legacy-id",
        ))
        await db.commit()

        result = await ingest_jobs([{
            "source": "indeed",
            "publisher_name": "Indeed",
            "collection_provider": "jsearch",
            "external_id": "legacy-id",
            "source_url": "https://indeed.com/viewjob?jk=legacy-id",
            "company_name": "Acme",
            "title_raw": "Data Analyst",
            "location_raw": "Remote",
        }], db)
        count = await db.scalar(select(func.count(JobSourceSighting.id)))
        refreshed = (await db.execute(
            select(JobPosting).options(selectinload(JobPosting.source_sightings))
        )).scalar_one()

    await engine.dispose()
    assert result["errors"] == 0
    assert count == 1
    assert refreshed.source_sightings[0].sighting_key == build_source_sighting_key(
        "indeed", "https://indeed.com/viewjob?jk=legacy-id", "legacy-id"
    )


def test_prepare_job_record_respects_database_text_capacities():
    record = prepare_job_record({
        "source": "jsearch",
        "collection_provider": "jsearch",
        "publisher_name": "Example Board",
        "external_id": "id-1",
        "source_url": "https://example.com/job/1?utm_source=test",
        "company_name": "C" * 400,
        "company_website": "https://example.com/" + ("path/" * 180),
        "title_raw": "T" * 800,
        "seniority": "S" * 80,
        "employment_type": "E" * 80,
        "specialization": "P" * 400,
        "location_raw": "L" * 700,
        "city": "C" * 300,
        "state": "S" * 150,
        "country": "U" * 150,
        "metro_area": "M" * 700,
        "salary_currency": "DOLLARS" * 5,
        "industry": "I" * 300,
    })

    assert len(record["company_name"]) == 255
    assert len(normalize_company_name(record["company_name"])) <= 255
    assert len(record["title_raw"]) == 500
    assert len(record["title_normalized"]) <= 500
    assert len(record["job_family"] or "") <= 500
    assert len(record["specialization"] or "") <= 300
    assert len(record["seniority"] or "") <= 50
    assert len(record["employment_type"] or "") <= 50
    assert len(record["location_raw"] or "") <= 500
    assert len(record["city"] or "") <= 200
    assert len(record["state"] or "") <= 100
    assert len(record["country"] or "") <= 100
    assert len(record["metro_area"] or "") <= 500
    assert len(record["salary_currency"]) <= 10
    assert len(record["company_website"] or "") <= 500
    assert len(record["industry"] or "") <= 200

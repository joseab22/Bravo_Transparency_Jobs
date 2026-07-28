from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.time import utc_now
from app.db.base import Base
from app.models.models import Company, JobPosting
from app.services.source_attribution import load_canonical_sources


@pytest.mark.asyncio
async def test_collapsed_sources_exclude_old_active_group_members(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'collapsed-age-filter.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    now = utc_now()

    async with Session() as db:
        company = Company(name="Wyetech", name_normalized="wyetech")
        db.add(company)
        await db.flush()

        old_job = JobPosting(
            company_id=company.id,
            job_identity_key="wyetech|software engineer 1|annapolis junction",
            source="simplify",
            publisher_name="Simplify",
            collection_provider="simplify",
            source_url="https://jobs.example.test/old",
            external_id="old-requisition",
            title_raw="Software Engineer 1",
            title_normalized="software engineer 1",
            location_raw="Annapolis Junction, MD",
            country="US",
            is_active=True,
            date_posted=now - timedelta(days=120),
            date_first_seen=now - timedelta(days=120),
            date_last_seen=now,
        )
        db.add(old_job)
        await db.flush()
        old_job.canonical_job_id = old_job.id

        recent_job = JobPosting(
            company_id=company.id,
            job_identity_key="wyetech|software engineer 1|annapolis junction|recent",
            source="company_site",
            publisher_name="Wyetech Careers",
            collection_provider="jsearch",
            source_url="https://jobs.example.test/recent",
            external_id="recent-requisition",
            title_raw="Software Engineer 1",
            title_normalized="software engineer 1",
            location_raw="Annapolis Junction, MD",
            country="US",
            is_active=True,
            date_posted=now - timedelta(days=10),
            date_first_seen=now - timedelta(days=10),
            date_last_seen=now,
            canonical_job_id=old_job.id,
        )
        db.add(recent_job)
        await db.commit()

        sources = await load_canonical_sources(
            [recent_job],
            db,
            max_age_days=30,
        )

    await engine.dispose()

    group_sources = sources[old_job.id]
    assert [source["source_url"] for source in group_sources] == [
        "https://jobs.example.test/recent"
    ]
    assert group_sources[0]["listing_ids"] == [recent_job.id]

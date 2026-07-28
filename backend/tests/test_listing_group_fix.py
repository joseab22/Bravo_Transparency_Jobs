from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.repost_detector import RepostDetectionService


def fake_job(**overrides):
    now = datetime(2026, 7, 5)
    values = dict(
        id=1,
        company_id=1,
        title_raw="Software Engineer 1",
        title_normalized="software engineer",
        job_family="software engineer",
        specialization=None,
        seniority="Mid",
        employment_type="Full-time",
        remote_type="Onsite",
        city="Annapolis Junction",
        state="MD",
        metro_area="Baltimore-Columbia-Towson, MD",
        location_raw="Annapolis Junction, MD",
        latitude=None,
        longitude=None,
        embedding=None,
        source="simplify",
        collection_provider="simplify",
        source_url="https://jobs.lever.co/wyetechllc/old",
        external_id="old",
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


def test_parallel_onsite_roles_use_specific_location_not_broad_metro():
    service = RepostDetectionService()
    first = fake_job()
    second = fake_job(
        id=2,
        title_raw="Software Engineer 1 (DM)",
        city="Linthicum Heights",
        location_raw="Linthicum Heights, MD",
        source_url="https://jobs.lever.co/wyetechllc/new",
        external_id="new",
        date_posted=first.date_posted + timedelta(hours=4),
    )

    assert service.classify_pair(second, first) == "original"


def test_same_provider_requisition_can_merge_across_location_labels():
    service = RepostDetectionService()
    first = fake_job(external_id="same-requisition")
    second = fake_job(
        id=2,
        city="Linthicum Heights",
        location_raw="Linthicum Heights, MD",
        external_id="same-requisition",
        date_posted=first.date_posted + timedelta(hours=4),
    )

    assert service.classify_pair(second, first) == "parallel"


@pytest.mark.asyncio
async def test_collapsed_sources_exclude_inactive_group_members():
    from app.services.source_attribution import load_canonical_sources

    group_id = 10
    expired = SimpleNamespace(
        id=10,
        canonical_job_id=group_id,
        is_active=False,
        source="simplify",
        publisher_name="Simplify",
        collection_provider="simplify",
        source_url="https://jobs.lever.co/wyetechllc/expired",
        external_id="expired",
        date_first_seen=datetime(2026, 7, 1),
        date_last_seen=datetime(2026, 7, 10),
        source_sightings=[],
    )
    active = SimpleNamespace(
        id=11,
        canonical_job_id=group_id,
        is_active=True,
        source="simplify",
        publisher_name="Simplify",
        collection_provider="simplify",
        source_url="https://jobs.lever.co/wyetechllc/active",
        external_id="active",
        date_first_seen=datetime(2026, 7, 2),
        date_last_seen=datetime(2026, 7, 11),
        source_sightings=[],
    )

    class FakeScalarResult:
        def __init__(self, members):
            self.members = members

        def unique(self):
            return self.members

    class FakeExecuteResult:
        def __init__(self, members):
            self.members = members

        def scalars(self):
            return FakeScalarResult(self.members)

    class FakeSession:
        async def execute(self, _query):
            return FakeExecuteResult([expired, active])

    sources = await load_canonical_sources([active], FakeSession())

    assert [item["source_url"] for item in sources[group_id]] == [
        "https://jobs.lever.co/wyetechllc/active"
    ]

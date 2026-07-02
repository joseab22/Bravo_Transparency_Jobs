"""Core unit tests — title decomposition, identity, repost classification, scoring."""

from datetime import datetime, timedelta

from app.services.normalizer import (
    build_identity_fingerprint,
    build_job_identity_key,
    decompose_title,
    extract_seniority,
    extract_skills,
    normalize_location_text,
    normalize_title,
)
from app.services.repost_detector import RepostDetectionService, classify_listing_pair
from app.services.scoring import ScoringService
from app.workers.ingestion import prepare_job_dict


class TestDecomposeTitle:
    def test_bi_alias(self):
        assert normalize_title("Business Intelligence Analyst") == "data analyst"

    def test_swe_alias(self):
        assert normalize_title("SWE II") == "software engineer"

    def test_ml_platform(self):
        parts = decompose_title("Staff ML Platform Engineer")
        assert parts["job_family"] == "machine learning engineer"
        assert parts["seniority"] == "lead"
        assert parts["specializations"] == ["platform"]

    def test_admin_and_lead_do_not_collapse(self):
        admin = decompose_title("Senior Software Engineer - Admin")
        lead = decompose_title("Senior Software Engineer - Lead")
        assert admin["job_family"] == lead["job_family"] == "software engineer"
        assert admin["seniority"] == lead["seniority"] == "senior"
        assert admin["specialization"] == "admin"
        assert lead["specialization"] == "tech_lead"

    def test_lead_prefix_is_seniority(self):
        parts = decompose_title("Lead Software Engineer")
        assert parts["seniority"] == "lead"
        assert parts["specialization"] is None

    def test_default_mid(self):
        assert extract_seniority("Data Analyst") == "mid"


class TestExtractSkills:
    def test_python_sql(self):
        skills = extract_skills("Must know Python and SQL.")
        names = {skill["skill"] for skill in skills}
        assert "Python" in names and "SQL" in names

    def test_empty(self):
        assert extract_skills("") == []

    def test_cloud_category(self):
        skills = extract_skills("Experience with AWS and Docker required.")
        categories = {skill["skill"]: skill["skill_category"] for skill in skills}
        assert categories["AWS"] == "Cloud"
        assert categories["Docker"] == "DevOps"


class TestJobIdentity:
    def test_specializations_produce_distinct_keys(self):
        admin = build_job_identity_key(
            "TechCorp",
            job_family="software engineer",
            specializations=["admin"],
            seniority="senior",
            metro_area="Los Angeles, California",
            remote_type="Onsite",
            employment_type="Full-time",
        )
        lead = build_job_identity_key(
            "TechCorp",
            job_family="software engineer",
            specializations=["tech_lead"],
            seniority="senior",
            metro_area="Los Angeles, California",
            remote_type="Onsite",
            employment_type="Full-time",
        )
        assert admin != lead

    def test_remote_identity_ignores_advertised_region(self):
        california = build_job_identity_key(
            "Acme", "software engineer", "California",
            remote_type="Remote", seniority="mid", employment_type="Full-time",
        )
        texas = build_job_identity_key(
            "Acme", "software engineer", "Texas",
            remote_type="Remote", seniority="mid", employment_type="Full-time",
        )
        assert california == texas

    def test_onsite_identity_keeps_metro(self):
        la = build_job_identity_key(
            "Acme", "software engineer", "Los Angeles, California",
            remote_type="Onsite", seniority="mid", employment_type="Full-time",
        )
        ny = build_job_identity_key(
            "Acme", "software engineer", "New York, New York",
            remote_type="Onsite", seniority="mid", employment_type="Full-time",
        )
        assert la != ny

    def test_fingerprint_is_location_independent(self):
        first = build_identity_fingerprint(
            "Acme", "software engineer", ["backend"], "senior", "Remote", "Full-time"
        )
        second = build_identity_fingerprint(
            "Acme", "software engineer", ["backend"], "senior", "Remote", "Full-time"
        )
        assert first == second and len(first) == 64


class FakeListing:
    def __init__(self, **kwargs):
        now = datetime.now()
        defaults = dict(
            id=1,
            company_id=10,
            canonical_job_id=None,
            source="indeed",
            external_id="a",
            title_raw="Senior Software Engineer - Backend",
            title_normalized="software engineer",
            job_family="software engineer",
            specialization="backend",
            title_parse_confidence=0.95,
            seniority="senior",
            employment_type="Full-time",
            remote_type="Remote",
            metro_area="California",
            latitude=None,
            longitude=None,
            date_posted=now,
            date_first_seen=now,
            date_last_seen=now,
            created_at=now,
            is_active=True,
            repost_count=0,
            identity_fingerprint="fingerprint",
        )
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(self, key, value)


class TestListingClassification:
    def test_same_external_id_is_duplicate(self):
        existing = FakeListing(id=1, external_id="same")
        new = FakeListing(id=2, external_id="same")
        assert classify_listing_pair(new, existing).classification == "duplicate"

    def test_concurrent_remote_regions_are_parallel(self):
        now = datetime.now()
        existing = FakeListing(
            id=1, external_id="ca", metro_area="California", date_posted=now
        )
        new = FakeListing(
            id=2, external_id="tx", metro_area="Texas", date_posted=now + timedelta(hours=12)
        )
        match = classify_listing_pair(new, existing)
        assert match.classification == "parallel"
        assert match.reason == "concurrent_remote_listing"

    def test_concurrent_different_onsite_metros_are_parallel_not_repost(self):
        now = datetime.now()
        existing = FakeListing(
            id=1,
            external_id="la",
            remote_type="Onsite",
            metro_area="Los Angeles, California",
            latitude=34.05,
            longitude=-118.24,
            date_posted=now,
        )
        new = FakeListing(
            id=2,
            external_id="ny",
            remote_type="Onsite",
            metro_area="New York, New York",
            latitude=40.71,
            longitude=-74.00,
            date_posted=now + timedelta(days=1),
        )
        match = classify_listing_pair(new, existing)
        assert match.classification == "parallel"
        assert match.reason == "concurrent_multi_location_listing"

    def test_closed_listing_returning_after_gap_is_repost(self):
        now = datetime.now()
        existing = FakeListing(
            id=1,
            external_id="old",
            is_active=False,
            date_posted=now - timedelta(days=30),
            date_first_seen=now - timedelta(days=30),
            date_last_seen=now - timedelta(days=10),
        )
        new = FakeListing(id=2, external_id="new", date_posted=now)
        match = classify_listing_pair(new, existing)
        assert match.classification == "repost"
        assert match.days_since_previous == 10

    def test_distinct_specializations_are_original(self):
        existing = FakeListing(id=1, specialization="admin")
        new = FakeListing(id=2, external_id="b", specialization="tech_lead")
        assert classify_listing_pair(new, existing).classification == "original"

    def test_different_onsite_metros_outside_parallel_window_are_original(self):
        now = datetime.now()
        existing = FakeListing(
            id=1,
            is_active=False,
            remote_type="Onsite",
            metro_area="Los Angeles, California",
            latitude=34.05,
            longitude=-118.24,
            date_posted=now - timedelta(days=30),
            date_last_seen=now - timedelta(days=10),
        )
        new = FakeListing(
            id=2,
            external_id="ny",
            remote_type="Onsite",
            metro_area="New York, New York",
            latitude=40.71,
            longitude=-74.00,
            date_posted=now,
        )
        assert classify_listing_pair(new, existing).classification == "original"

    def test_quick_reactivation_is_parallel(self):
        now = datetime.now()
        existing = FakeListing(
            id=1,
            is_active=False,
            date_posted=now - timedelta(days=10),
            date_last_seen=now - timedelta(days=3),
        )
        new = FakeListing(id=2, external_id="new", date_posted=now)
        match = classify_listing_pair(new, existing)
        assert match.classification == "parallel"
        assert match.reason == "quick_reactivation"


class TestDescriptionValidation:
    def setup_method(self):
        self.service = RepostDetectionService()

    def test_under_specified_roles_require_description_similarity(self):
        existing = FakeListing(id=1, specialization=None)
        new = FakeListing(id=2, external_id="new", specialization=None)
        assert not self.service._semantic_match_is_plausible(new, existing, 0.20)
        assert self.service._semantic_match_is_plausible(new, existing, 0.90)

    def test_known_specialization_does_not_require_description_fallback(self):
        existing = FakeListing(id=1, specialization="backend")
        new = FakeListing(id=2, external_id="new", specialization="backend")
        assert self.service._semantic_match_is_plausible(new, existing, 0.20)


class TestCentralIdentityPreparation:
    def test_ingestion_recomputes_legacy_scraper_identity(self):
        prepared = prepare_job_dict({
            "source": "indeed",
            "external_id": "123",
            "company_name": "Acme, Inc.",
            "title_raw": "Senior Software Engineer - Admin",
            "title_normalized": "incorrect legacy title",
            "job_identity_key": "legacy-key",
            "metro_area": "Texas",
            "remote_type": "Remote",
            "employment_type": "Full-time",
        })
        assert prepared["job_family"] == "software engineer"
        assert prepared["specialization"] == "admin"
        assert prepared["seniority"] == "senior"
        assert prepared["job_identity_key"] != "legacy-key"
        assert prepared["job_identity_key"].endswith("__remote")
        assert len(prepared["identity_fingerprint"]) == 64


class TestLocationNorm:
    def test_common_aliases(self):
        assert normalize_location_text("la") == "Los Angeles"
        assert normalize_location_text("sf") == "San Francisco"
        assert normalize_location_text("nyc") == "New York"


class FakeJob:
    def __init__(self, **kwargs):
        defaults = dict(
            repost_count=0,
            days_active=5,
            applicant_count=30,
            salary_listed=True,
            company=None,
            ghost_job_probability=0.1,
            salary_min=80000,
            salary_max=100000,
            job_identity_key="test__analyst__la",
            listing_classification="original",
        )
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(self, key, value)


class TestScoringService:
    def setup_method(self):
        self.scorer = ScoringService()

    def test_health_score_in_range(self):
        score = self.scorer._health_score(FakeJob(), ghost_prob=0.1)
        assert 0 <= score <= 100

    def test_high_ghost_lowers_health(self):
        good = self.scorer._health_score(FakeJob(days_active=3), ghost_prob=0.05)
        bad = self.scorer._health_score(
            FakeJob(days_active=200, applicant_count=2000, salary_listed=False),
            ghost_prob=0.92,
        )
        assert good > bad

    def test_parallel_listing_raises_activity(self):
        baseline_job = FakeJob(days_active=20, salary_listed=False)
        parallel_job = FakeJob(
            days_active=20, salary_listed=False, listing_classification="parallel"
        )
        original = self.scorer._activity_score(baseline_job, related_active=1)
        parallel = self.scorer._activity_score(parallel_job, related_active=3)
        assert parallel > original

    def test_active_hiring_confidence_in_range(self):
        score = self.scorer._active_hiring_confidence(
            FakeJob(), ghost_prob=0.1, activity_score=90, applicant_trend=5, related_active=2
        )
        assert 0 <= score <= 100

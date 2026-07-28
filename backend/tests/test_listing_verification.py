from app.services.listing_verification import (
    URLCheckResult,
    classify_page,
    combine_url_results,
)


def test_http_404_is_inactive():
    result = classify_page(
        original_url="https://example.com/jobs/123",
        final_url="https://example.com/jobs/123",
        status_code=404,
        text="",
        redirected=False,
    )
    assert result.outcome == "inactive"


def test_expired_message_is_inactive():
    result = classify_page(
        original_url="https://example.com/jobs/123",
        final_url="https://example.com/jobs/123",
        status_code=200,
        text="This job is no longer available.",
        redirected=False,
    )
    assert result.outcome == "inactive"


def test_access_block_is_unknown():
    result = classify_page(
        original_url="https://example.com/jobs/123",
        final_url="https://example.com/jobs/123",
        status_code=403,
        text="Access denied",
        redirected=False,
    )
    assert result.outcome == "unknown"


def test_successful_normal_page_is_active():
    result = classify_page(
        original_url="https://example.com/jobs/123",
        final_url="https://example.com/jobs/123",
        status_code=200,
        text="Software Engineer. Apply for this job.",
        redirected=False,
    )
    assert result.outcome == "active"


def test_one_active_source_keeps_job_active():
    result = combine_url_results(
        1,
        [
            URLCheckResult("https://a.test", "inactive", "closed", 404),
            URLCheckResult("https://b.test", "active", "loaded", 200),
        ],
    )
    assert result.outcome == "active"


def test_unknown_source_prevents_automatic_deactivation():
    result = combine_url_results(
        1,
        [
            URLCheckResult("https://a.test", "inactive", "closed", 404),
            URLCheckResult("https://b.test", "unknown", "blocked", 403),
        ],
    )
    assert result.outcome == "unknown"


def test_all_sources_must_be_inactive_to_deactivate():
    result = combine_url_results(
        1,
        [
            URLCheckResult("https://a.test", "inactive", "closed", 404),
            URLCheckResult("https://b.test", "inactive", "expired", 410),
        ],
    )
    assert result.outcome == "inactive"

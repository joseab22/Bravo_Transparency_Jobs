"""Structured identity resolution for original, parallel, and repost listings."""
from __future__ import annotations

from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.time import utc_now
from app.models.models import JobPosting, RepostEvent
from app.services.normalizer import (
    IDENTITY_DEFINING_SPECIALIZATIONS,
    build_identity_fingerprint,
    build_job_identity_key,
    decompose_title,
    locations_in_same_cluster,
    normalize_company_name,
    normalize_location_text,
    specialization_sets_conflict,
)

log = structlog.get_logger()
_model = None

SCORE_FIELDS = (
    "ghost_job_probability", "ghost_confidence", "health_score",
    "competition_score", "interview_opportunity_score", "salary_fairness_score",
    "market_salary", "stability_score", "activity_score",
    "active_hiring_confidence", "description_change_score", "applicant_trend",
    "salary_trend",
)


def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_text(text: str) -> list[float]:
    return get_embedding_model().encode(text, normalize_embeddings=True).tolist()


def lexical_title_similarity(title_a: str, title_b: str) -> float:
    a, b = (title_a or "").strip().lower(), (title_b or "").strip().lower()
    if not a or not b:
        return 0.0
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def title_similarity(title_a: str, title_b: str) -> float:
    """Return a bounded title similarity without downloading a model by default.

    Structured title fields are the primary identity signal. Semantic title
    embeddings are opt-in because loading a model inside a large historical
    classification pass can otherwise dominate runtime and memory.
    """
    lexical = lexical_title_similarity(title_a, title_b)
    if lexical in {0.0, 1.0} or not settings.semantic_title_matching_enabled:
        return lexical
    try:
        vectors = get_embedding_model().encode(
            [title_a or "", title_b or ""], normalize_embeddings=True
        )
        return float(np.dot(vectors[0], vectors[1]))
    except Exception as exc:
        log.warning("title_embedding_fallback", error=str(exc))
        return lexical


def _description_similarity(a: JobPosting, b: JobPosting) -> Optional[float]:
    if not a.embedding or not b.embedding:
        return None
    av, bv = np.asarray(a.embedding.vector), np.asarray(b.embedding.vector)
    if not av.size or not bv.size:
        return None
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return float(np.dot(av, bv) / denom) if denom else None


def _specialty_set(job: JobPosting) -> set[str]:
    return {part.strip() for part in (job.specialization or "").split(",") if part.strip()}


def _work_arrangement_compatible(a: JobPosting, b: JobPosting) -> bool:
    first, second = a.remote_type or "Onsite", b.remote_type or "Onsite"
    if {first, second} == {"Remote", "Onsite"}:
        return False
    return True


def _same_source_requisition(a: JobPosting, b: JobPosting) -> bool:
    """Return True only when provider identifiers point to the same requisition."""
    first_url = (getattr(a, "source_url", None) or "").strip()
    second_url = (getattr(b, "source_url", None) or "").strip()
    if first_url and second_url and first_url == second_url:
        return True

    first_external = (getattr(a, "external_id", None) or "").strip()
    second_external = (getattr(b, "external_id", None) or "").strip()
    if not first_external or first_external != second_external:
        return False

    first_provider = (
        getattr(a, "collection_provider", None)
        or getattr(a, "source", None)
        or ""
    )
    second_provider = (
        getattr(b, "collection_provider", None)
        or getattr(b, "source", None)
        or ""
    )
    return bool(first_provider and first_provider == second_provider)


def _specific_location(job: JobPosting) -> str:
    """Prefer the named posting location over a broader metro bucket."""
    city = (getattr(job, "city", None) or "").strip()
    state = (getattr(job, "state", None) or "").strip()
    if city:
        return (normalize_location_text(
            ", ".join(part for part in (city, state) if part)
        ) or "").lower()
    return (normalize_location_text(getattr(job, "location_raw", None)) or "").lower()


def _locations_compatible(a: JobPosting, b: JobPosting, *, parallel: bool) -> bool:
    if not _work_arrangement_compatible(a, b):
        return False
    if a.remote_type == b.remote_type == "Remote":
        return True
    if _same_source_requisition(a, b):
        return True

    exact_left = _specific_location(a)
    exact_right = _specific_location(b)

    if parallel:
        # Simultaneous onsite openings with different named locations are
        # separate requisitions, even when both locations belong to the same
        # broader metro area.
        if exact_left and exact_right:
            return exact_left == exact_right
        metro_left = (normalize_location_text(a.metro_area) or "").lower()
        metro_right = (normalize_location_text(b.metro_area) or "").lower()
        return bool(metro_left and metro_right and metro_left == metro_right)

    # A later repost may move within a local hiring area after the earlier
    # requisition closes, so proximity remains useful only for repost matching.
    if locations_in_same_cluster(a.latitude, a.longitude, b.latitude, b.longitude):
        return True
    if exact_left and exact_right:
        return exact_left == exact_right
    metro_left = (normalize_location_text(a.metro_area) or "").lower()
    metro_right = (normalize_location_text(b.metro_area) or "").lower()
    return bool(metro_left and metro_right and metro_left == metro_right)


def _posted_at(job: JobPosting) -> datetime:
    return job.date_posted or job.date_first_seen or job.created_at or utc_now()


def _invalidate_scores(job: JobPosting) -> None:
    for field in SCORE_FIELDS:
        setattr(job, field, None)


class RepostDetectionService:
    def roles_match(self, new_job: JobPosting, old_job: JobPosting) -> bool:
        if new_job.company_id != old_job.company_id:
            return False
        if not _work_arrangement_compatible(new_job, old_job):
            return False
        if new_job.employment_type and old_job.employment_type and new_job.employment_type != old_job.employment_type:
            return False
        if new_job.seniority and old_job.seniority and new_job.seniority != old_job.seniority:
            return False

        family_a, family_b = new_job.job_family, old_job.job_family
        if family_a and family_b and family_a != family_b:
            return False

        spec_a, spec_b = _specialty_set(new_job), _specialty_set(old_job)
        if specialization_sets_conflict(spec_a, spec_b):
            return False

        # Compare the original titles as well as the normalized family. The
        # normalized titles may both be "software engineer" even when the raw
        # titles identify different requisitions.
        normalized_title_sim = title_similarity(
            new_job.title_normalized, old_job.title_normalized
        )
        raw_title_sim = lexical_title_similarity(
            getattr(new_job, "title_raw", new_job.title_normalized),
            getattr(old_job, "title_raw", old_job.title_normalized),
        )
        desc_sim = _description_similarity(new_job, old_job)

        if family_a and family_b:
            if bool(spec_a) != bool(spec_b):
                specialized = spec_a or spec_b
                has_identity_defining_tag = bool(
                    specialized.intersection(IDENTITY_DEFINING_SPECIALIZATIONS)
                )
                if has_identity_defining_tag:
                    # A generic title must not absorb a specialized title based
                    # only on their shared broad family. Permit the match only
                    # when both the raw title and description provide strong
                    # independent evidence.
                    return (
                        raw_title_sim >= 0.88
                        and desc_sim is not None
                        and desc_sim >= settings.description_similarity_threshold
                    )
                return raw_title_sim >= 0.90

            if spec_a and spec_b and spec_a.isdisjoint(spec_b):
                # Disjoint non-conflicting tags are still insufficient on their
                # own; require very similar raw titles and descriptions.
                return (
                    raw_title_sim >= 0.90
                    and desc_sim is not None
                    and desc_sim >= settings.description_similarity_threshold
                )

            if desc_sim is not None and desc_sim < settings.description_similarity_threshold and raw_title_sim < 0.75:
                return False
            return raw_title_sim >= 0.72 or normalized_title_sim >= settings.similarity_threshold
        if normalized_title_sim < settings.similarity_threshold:
            return False
        return desc_sim is None or desc_sim >= settings.description_similarity_threshold

    def classify_pair(self, new_job: JobPosting, old_job: JobPosting) -> str:
        if not self.roles_match(new_job, old_job):
            return "original"

        new_date, old_date = _posted_at(new_job), _posted_at(old_job)
        gap = abs((new_date - old_date).days)
        overlaps = bool(old_job.is_active) or old_job.date_last_seen >= new_job.date_first_seen
        parallel = overlaps or gap <= settings.parallel_listing_window_days
        if parallel and _locations_compatible(new_job, old_job, parallel=True):
            return "parallel"

        inactive_before_new = not old_job.is_active and old_job.date_last_seen < new_job.date_first_seen
        elapsed = (new_job.date_first_seen - old_job.date_last_seen).days
        if inactive_before_new and elapsed >= settings.repost_min_gap_days and _locations_compatible(new_job, old_job, parallel=False):
            return "repost"
        return "original"

    async def run_full_detection(self, db: AsyncSession) -> dict:
        cutoff = utc_now() - timedelta(days=settings.candidate_history_days)
        result = await db.execute(
            select(JobPosting)
            .options(selectinload(JobPosting.company), selectinload(JobPosting.embedding))
            .where(JobPosting.date_first_seen >= cutoff)
            .order_by(JobPosting.company_id, JobPosting.date_first_seen, JobPosting.id)
        )
        jobs = list(result.scalars().unique())

        processed_ids = [job.id for job in jobs]
        if processed_ids:
            await db.execute(
                delete(RepostEvent).where(RepostEvent.job_posting_id.in_(processed_ids))
            )
        buckets: dict[tuple[int, str, str, str, str], list[JobPosting]] = {}
        counts = {"original": 0, "parallel": 0, "repost": 0}
        changed = 0

        for job in jobs:
            parts = decompose_title(job.title_raw)
            job.job_family = parts["job_family"] or parts["title_normalized"]
            job.specialization = parts["specialization"]
            job.seniority = job.seniority or parts["seniority"]
            job.title_normalized = parts["title_normalized"]
            job.title_parse_confidence = parts["confidence"]
            job.identity_fingerprint = build_identity_fingerprint(
                job.company.name if job.company else job.company_id,
                job.job_family, job.specialization, job.seniority,
                job.employment_type, job.remote_type,
            )
            job.job_identity_key = build_job_identity_key(
                job.company.name if job.company else job.company_id,
                job.job_family, job.metro_area,
                specialization=job.specialization, seniority=job.seniority,
                employment_type=job.employment_type, remote_type=job.remote_type,
            )

            work_bucket = "remote" if job.remote_type == "Remote" else "site"
            key = (
                job.company_id,
                job.job_family or job.title_normalized,
                job.seniority or "",
                job.employment_type or "",
                work_bucket,
            )
            candidates = buckets.setdefault(key, [])
            classification, canonical = "original", job
            recent_candidates = candidates[-settings.identity_candidate_limit :]
            for candidate in reversed(recent_candidates):
                current = self.classify_pair(job, candidate)
                if current in {"parallel", "repost"}:
                    classification = current
                    canonical_id = candidate.canonical_job_id or candidate.id
                    canonical = next((x for x in candidates if x.id == canonical_id), candidate)
                    break

            previous_state = (job.listing_classification, job.canonical_job_id, job.repost_count)
            job.listing_classification = classification
            job.canonical_job_id = canonical.id if canonical.id else job.id
            if classification == "repost":
                prior_reposts = canonical.repost_count or 0
                job.repost_count = prior_reposts + 1
                canonical.repost_count = job.repost_count
                db.add(RepostEvent(
                    job_posting_id=job.id,
                    job_identity_key=job.job_identity_key,
                    occurrence_number=job.repost_count,
                    date_seen=job.date_first_seen,
                    source=job.source,
                    days_since_previous=max((job.date_first_seen - canonical.date_last_seen).days, 0),
                ))
            else:
                job.repost_count = canonical.repost_count or 0 if classification == "parallel" else 0

            if previous_state != (job.listing_classification, job.canonical_job_id, job.repost_count):
                changed += 1
                _invalidate_scores(job)
            counts[classification] += 1
            candidates.append(job)

        await db.flush()
        return {"jobs_processed": len(jobs), "jobs_changed": changed, **counts}

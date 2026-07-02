"""
Identity resolution and repost classification.

A related listing is classified as:
  * duplicate: same source and stable external ID (normally handled by ingestion)
  * parallel: same hiring effort advertised concurrently, including remote or
    multi-location copies with different external IDs
  * repost: a prior related listing was inactive and returned after the
    configured minimum gap
  * original: no sufficiently related earlier listing

Rules handle known structured fields first. Sentence-transformer similarity is
used only as a fallback when the title taxonomy is uncertain.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.models import EventType, JobEmbedding, JobEvent, JobPosting, RepostEvent
from app.services.normalizer import (
    build_identity_fingerprint,
    build_job_identity_key,
    decompose_title,
    is_remote,
    locations_in_same_cluster,
)

import structlog

log = structlog.get_logger()

_model = None


@dataclass(frozen=True)
class ListingMatch:
    classification: str
    related_job_id: Optional[int] = None
    reason: str = ""
    days_since_previous: Optional[int] = None
    title_similarity: Optional[float] = None
    description_similarity: Optional[float] = None


def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_text(text: str) -> list[float]:
    return get_embedding_model().encode(text, normalize_embeddings=True).tolist()


def title_similarity(title_a: str, title_b: str) -> float:
    embeddings = get_embedding_model().encode(
        [title_a or "", title_b or ""], normalize_embeddings=True
    )
    return float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])


def description_similarity(emb_a: list[float], emb_b: list[float]) -> float:
    a = np.array(emb_a).reshape(1, -1)
    b = np.array(emb_b).reshape(1, -1)
    return float(cosine_similarity(a, b)[0][0])


def _posting_time(job: JobPosting) -> datetime:
    return job.date_posted or job.date_first_seen or job.created_at or datetime.utcnow()


def _specialization_set(job: JobPosting) -> set[str]:
    value = getattr(job, "specialization", None)
    if not value:
        return set()
    return {part.strip() for part in value.replace("|", ",").split(",") if part.strip()}


def _role_compatible(new_job: JobPosting, existing_job: JobPosting) -> tuple[bool, Optional[float]]:
    """Return whether role structure is compatible and optional semantic score."""
    new_family = getattr(new_job, "job_family", None) or new_job.title_normalized
    old_family = getattr(existing_job, "job_family", None) or existing_job.title_normalized

    new_specs = _specialization_set(new_job)
    old_specs = _specialization_set(existing_job)

    # Distinct known specializations should not collapse (admin vs tech_lead).
    if new_specs and old_specs and new_specs.isdisjoint(old_specs):
        return False, None

    # Explicit seniority differences normally represent separate requisitions.
    if new_job.seniority and existing_job.seniority and new_job.seniority != existing_job.seniority:
        return False, None

    if (
        new_job.employment_type
        and existing_job.employment_type
        and new_job.employment_type != existing_job.employment_type
    ):
        return False, None

    if new_family == old_family:
        return True, 1.0

    # Only use the model when at least one parse was uncertain.
    new_conf = getattr(new_job, "title_parse_confidence", None) or 0.0
    old_conf = getattr(existing_job, "title_parse_confidence", None) or 0.0
    if min(new_conf, old_conf) >= 0.8:
        return False, None

    similarity = title_similarity(new_job.title_raw, existing_job.title_raw)
    return similarity >= settings.similarity_threshold, similarity


def _location_relation(new_job: JobPosting, existing_job: JobPosting) -> str:
    """Return same, different, or unknown for geographic compatibility."""
    new_remote = is_remote(new_job.remote_type)
    old_remote = is_remote(existing_job.remote_type)

    if new_remote and old_remote:
        return "same"
    if new_remote != old_remote:
        return "different"

    coordinates_present = all([
        new_job.latitude is not None,
        new_job.longitude is not None,
        existing_job.latitude is not None,
        existing_job.longitude is not None,
    ])
    if coordinates_present:
        return "same" if locations_in_same_cluster(
            new_job.latitude,
            new_job.longitude,
            existing_job.latitude,
            existing_job.longitude,
        ) else "different"

    new_metro = (new_job.metro_area or "").strip().lower()
    old_metro = (existing_job.metro_area or "").strip().lower()
    if new_metro and old_metro:
        return "same" if new_metro == old_metro else "different"
    return "unknown"


def classify_listing_pair(
    new_job: JobPosting,
    existing_job: JobPosting,
) -> ListingMatch:
    """Classify a new listing against one earlier listing."""
    if new_job.company_id != existing_job.company_id:
        return ListingMatch("original", reason="different_company")

    if (
        new_job.source == existing_job.source
        and new_job.external_id
        and new_job.external_id == existing_job.external_id
    ):
        return ListingMatch("duplicate", existing_job.id, "same_source_external_id")

    role_matches, semantic_score = _role_compatible(new_job, existing_job)
    if not role_matches:
        return ListingMatch("original", reason="different_role", title_similarity=semantic_score)

    new_time = _posting_time(new_job)
    old_time = _posting_time(existing_job)
    posting_delta = abs((new_time - old_time).days)
    location_relation = _location_relation(new_job, existing_job)

    # Different external IDs released together are concurrent openings or
    # multi-location advertisements—not reposts.
    if posting_delta <= settings.parallel_listing_window_days:
        reason = "concurrent_listing"
        if location_relation == "different":
            reason = "concurrent_multi_location_listing"
        elif is_remote(new_job.remote_type) and is_remote(existing_job.remote_type):
            reason = "concurrent_remote_listing"
        return ListingMatch(
            "parallel",
            existing_job.id,
            reason,
            title_similarity=semantic_score,
        )

    # An actively observed prior listing cannot be a repost. For the same
    # remote role or same metro, retain it as a parallel active opening.
    if existing_job.is_active and location_relation in {"same", "unknown"}:
        return ListingMatch(
            "parallel",
            existing_job.id,
            "overlapping_active_listing",
            title_similarity=semantic_score,
        )

    # A true repost requires a closed prior listing and a meaningful gap.
    previous_end = existing_job.date_last_seen or old_time
    gap_days = (new_time - previous_end).days
    if (
        not existing_job.is_active
        and gap_days >= settings.repost_min_gap_days
        and location_relation in {"same", "unknown"}
    ):
        return ListingMatch(
            "repost",
            existing_job.id,
            "inactive_listing_returned",
            days_since_previous=gap_days,
            title_similarity=semantic_score,
        )

    # Quick reopening before the gap threshold is treated as one ongoing
    # hiring effort, not a suspicious repost.
    if not existing_job.is_active and 0 <= gap_days < settings.repost_min_gap_days:
        return ListingMatch(
            "parallel",
            existing_job.id,
            "quick_reactivation",
            days_since_previous=gap_days,
            title_similarity=semantic_score,
        )

    return ListingMatch("original", reason="separate_location_or_timeline")


class RepostDetectionService:
    async def _candidate_jobs(self, job: JobPosting, db: AsyncSession) -> list[JobPosting]:
        """Fetch likely related jobs without requiring an identical location key."""
        family = getattr(job, "job_family", None) or job.title_normalized
        result = await db.execute(
            select(JobPosting)
            .where(
                and_(
                    JobPosting.company_id == job.company_id,
                    JobPosting.id != job.id,
                    or_(
                        JobPosting.identity_fingerprint == job.identity_fingerprint,
                        JobPosting.job_family == family,
                        JobPosting.title_normalized == job.title_normalized,
                    ),
                )
            )
            .order_by(JobPosting.date_first_seen.desc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def _description_similarity_map(
        self,
        job: JobPosting,
        candidates: list[JobPosting],
        db: AsyncSession,
    ) -> dict[int, float]:
        ids = [job.id, *[candidate.id for candidate in candidates]]
        result = await db.execute(
            select(JobEmbedding.job_posting_id, JobEmbedding.vector).where(
                JobEmbedding.job_posting_id.in_(ids)
            )
        )
        vectors = {row[0]: list(row[1]) for row in result.fetchall()}
        new_vector = vectors.get(job.id)
        if new_vector is None:
            return {}
        return {
            candidate.id: description_similarity(new_vector, vectors[candidate.id])
            for candidate in candidates
            if candidate.id in vectors
        }

    def _semantic_match_is_plausible(
        self,
        job: JobPosting,
        candidate: JobPosting,
        score: Optional[float],
    ) -> bool:
        if score is None:
            return True
        # Descriptions are most useful when titles lack specializations. Known
        # distinct specializations were already rejected by _role_compatible.
        underspecified = not _specialization_set(job) or not _specialization_set(candidate)
        return not underspecified or score >= settings.description_similarity_threshold

    async def is_repost_of(self, new_job: JobPosting, existing_job: JobPosting) -> bool:
        return classify_listing_pair(new_job, existing_job).classification == "repost"

    async def process_new_posting(self, job: JobPosting, db: AsyncSession) -> ListingMatch:
        candidates = await self._candidate_jobs(job, db)
        if not candidates:
            job.listing_classification = "original"
            job.canonical_job_id = job.id
            await db.flush()
            return ListingMatch("original", reason="first_seen_identity")

        description_scores = await self._description_similarity_map(job, candidates, db)
        evaluated: list[tuple[ListingMatch, JobPosting]] = []
        for candidate in candidates:
            match = classify_listing_pair(job, candidate)
            description_score = description_scores.get(candidate.id)
            match = replace(match, description_similarity=description_score)
            if (
                match.classification not in {"original", "duplicate"}
                and not self._semantic_match_is_plausible(job, candidate, description_score)
            ):
                match = ListingMatch(
                    "original",
                    reason="description_semantic_mismatch",
                    title_similarity=match.title_similarity,
                    description_similarity=description_score,
                )
            evaluated.append((match, candidate))

        # Prefer duplicate, then current parallel evidence, then a true repost.
        # Within a class, the strongest available description similarity wins.
        def best(classification: str):
            choices = [item for item in evaluated if item[0].classification == classification]
            if not choices:
                return None
            return max(choices, key=lambda item: item[0].description_similarity or -1.0)

        selected = best("duplicate") or best("parallel") or best("repost")
        if selected:
            preferred, related = selected
        else:
            preferred = ListingMatch("original", reason="no_related_match")
            related = None
        root_id = None
        if related is not None:
            root_id = related.canonical_job_id or related.id

        job.listing_classification = preferred.classification
        job.canonical_job_id = root_id or job.id

        if preferred.classification == "repost" and related is not None:
            max_count = max((candidate.repost_count or 0 for candidate in candidates), default=0)
            job.repost_count = max_count + 1
            db.add(RepostEvent(
                job_posting_id=job.id,
                job_identity_key=job.job_identity_key,
                occurrence_number=job.repost_count,
                date_seen=job.date_first_seen or datetime.utcnow(),
                source=job.source,
                days_since_previous=preferred.days_since_previous,
            ))
            db.add(JobEvent(
                job_posting_id=job.id,
                event_type=EventType.reposted,
                source=job.source,
                payload={
                    "canonical_job_id": job.canonical_job_id,
                    "previous_job_id": related.id,
                    "days_since_previous": preferred.days_since_previous,
                    "reason": preferred.reason,
                    "description_similarity": preferred.description_similarity,
                },
            ))
            log.info(
                "repost_detected",
                job_id=job.id,
                previous_job_id=related.id,
                repost_count=job.repost_count,
                reason=preferred.reason,
            )
        elif preferred.classification == "parallel" and related is not None:
            job.repost_count = related.repost_count or 0
            db.add(JobEvent(
                job_posting_id=job.id,
                event_type=EventType.source_added,
                source=job.source,
                payload={
                    "classification": "parallel",
                    "canonical_job_id": job.canonical_job_id,
                    "related_job_id": related.id,
                    "reason": preferred.reason,
                    "description_similarity": preferred.description_similarity,
                },
            ))
            log.info(
                "parallel_listing_detected",
                job_id=job.id,
                related_job_id=related.id,
                reason=preferred.reason,
            )

        await db.flush()
        return preferred

    async def run_full_detection(self, db: AsyncSession) -> dict:
        """Backfill classifications in chronological order without double-counting events."""
        result = await db.execute(
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .order_by(JobPosting.company_id, JobPosting.date_first_seen, JobPosting.id)
        )
        jobs = list(result.scalars().all())

        # Rebuild structured identities so records created before migration 0002
        # receive the same logic as newly ingested records.
        for job in jobs:
            parts = decompose_title(job.title_raw)
            job.title_normalized = parts["title_normalized"]
            job.job_family = parts["job_family"]
            job.specialization = parts["specialization"]
            job.title_parse_confidence = parts["parse_confidence"]
            job.seniority = parts["seniority"]
            company_name = job.company.name if job.company else str(job.company_id)
            job.job_identity_key = build_job_identity_key(
                company_name,
                job_family=parts["job_family"],
                specializations=parts["specializations"],
                seniority=parts["seniority"],
                metro_area=job.metro_area,
                remote_type=job.remote_type,
                employment_type=job.employment_type,
            )
            job.identity_fingerprint = build_identity_fingerprint(
                company_name,
                parts["job_family"],
                parts["specializations"],
                parts["seniority"],
                job.remote_type,
                job.employment_type,
            )

        embedding_result = await db.execute(
            select(JobEmbedding.job_posting_id, JobEmbedding.vector)
        )
        embedding_vectors = {
            row[0]: list(row[1])
            for row in embedding_result.fetchall()
            if row[1] is not None
        }

        prior_by_company: dict[int, list[JobPosting]] = {}
        counts = {"original": 0, "parallel": 0, "repost": 0}

        for job in jobs:
            prior = prior_by_company.setdefault(job.company_id, [])
            evaluated: list[tuple[ListingMatch, JobPosting]] = []
            new_vector = embedding_vectors.get(job.id)

            for candidate in reversed(prior[-100:]):
                match = classify_listing_pair(job, candidate)
                candidate_vector = embedding_vectors.get(candidate.id)
                semantic_score = None
                if new_vector is not None and candidate_vector is not None:
                    semantic_score = description_similarity(new_vector, candidate_vector)
                    match = replace(match, description_similarity=semantic_score)

                if (
                    match.classification not in {"original", "duplicate"}
                    and not self._semantic_match_is_plausible(job, candidate, semantic_score)
                ):
                    match = ListingMatch(
                        "original",
                        reason="description_semantic_mismatch",
                        title_similarity=match.title_similarity,
                        description_similarity=semantic_score,
                    )
                evaluated.append((match, candidate))

            def choose(classification: str):
                choices = [item for item in evaluated if item[0].classification == classification]
                if not choices:
                    return None
                return max(
                    choices,
                    key=lambda item: item[0].description_similarity or -1.0,
                )

            selected = choose("duplicate") or choose("parallel") or choose("repost")
            if selected:
                match, related = selected
            else:
                match = ListingMatch("original", reason="backfill_first_identity")
                related = None

            job.listing_classification = match.classification
            job.canonical_job_id = (related.canonical_job_id or related.id) if related else job.id
            if match.classification == "repost":
                related_chain = [
                    candidate
                    for candidate in prior
                    if (candidate.canonical_job_id or candidate.id) == job.canonical_job_id
                ]
                prior_count = max(
                    (candidate.repost_count or 0 for candidate in related_chain),
                    default=0,
                )
                job.repost_count = prior_count + 1
            elif related:
                job.repost_count = related.repost_count or 0
            else:
                job.repost_count = 0

            counts[match.classification] += 1
            prior.append(job)

        await db.flush()
        return {
            "jobs_processed": len(jobs),
            "original_listings": counts["original"],
            "parallel_listings": counts["parallel"],
            "reposts": counts["repost"],
        }

"""
Repost detection service.

Two postings are treated as the same role (and thus a repost) when:
  1. Same company
  2. Normalized title cosine similarity > threshold (default 0.85)
  3. Same metro cluster (within 40 miles)

When a job_identity_key disappears and reappears → repost_count += 1
and a RepostEvent is written.
"""

from datetime import datetime
from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.models import JobPosting, RepostEvent
from app.services.normalizer import locations_in_same_cluster, build_job_identity_key
from app.core.config import settings

import structlog

log = structlog.get_logger()

_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def title_similarity(title_a: str, title_b: str) -> float:
    model = get_embedding_model()
    embeddings = model.encode([title_a, title_b], normalize_embeddings=True)
    return float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])


def description_similarity(emb_a: list[float], emb_b: list[float]) -> float:
    a = np.array(emb_a).reshape(1, -1)
    b = np.array(emb_b).reshape(1, -1)
    return float(cosine_similarity(a, b)[0][0])


class RepostDetectionService:

    async def is_repost_of(
        self,
        new_job: JobPosting,
        existing_job: JobPosting,
    ) -> bool:
        """
        Returns True if new_job is a repost of existing_job.
        Uses 3-way check: company, title similarity, location cluster.
        """
        # 1. Must be same company
        if new_job.company_id != existing_job.company_id:
            return False

        # 2. Title similarity
        sim = title_similarity(new_job.title_normalized, existing_job.title_normalized)
        if sim < settings.similarity_threshold:
            return False

        # 3. Location cluster
        if (new_job.remote_type == "Remote" and existing_job.remote_type == "Remote"):
            return True  # both remote → same role

        if (new_job.latitude and new_job.longitude and
                existing_job.latitude and existing_job.longitude):
            if not locations_in_same_cluster(
                new_job.latitude, new_job.longitude,
                existing_job.latitude, existing_job.longitude,
            ):
                return False

        return True

    async def process_new_posting(
        self, job: JobPosting, db: AsyncSession
    ) -> int:
        """
        Check if this posting is a repost of an existing role.
        Updates repost_count and writes RepostEvent if so.
        Returns the total repost count.
        """
        # Find all other postings with the same identity key
        result = await db.execute(
            select(JobPosting).where(
                and_(
                    JobPosting.job_identity_key == job.job_identity_key,
                    JobPosting.id != job.id,
                )
            )
        )
        related = result.scalars().all()

        if not related:
            return 0

        # Count existing repost events for this key
        event_count_result = await db.execute(
            select(func.count(RepostEvent.id)).where(
                RepostEvent.job_identity_key == job.job_identity_key
            )
        )
        existing_events = event_count_result.scalar_one() or 0

        # This is a new repost
        event = RepostEvent(
            job_posting_id=job.id,
            job_identity_key=job.job_identity_key,
            occurrence_number=existing_events + 1,
            date_seen=datetime.utcnow(),
            source=job.source,
        )
        db.add(event)

        new_repost_count = existing_events + 1
        job.repost_count = new_repost_count

        log.info(
            "repost_detected",
            job_identity_key=job.job_identity_key,
            repost_count=new_repost_count,
            job_id=job.id,
        )

        await db.flush()
        return new_repost_count

    async def run_full_detection(self, db: AsyncSession) -> dict:
        """
        Run repost detection across all active postings.
        Called by the Celery beat task.
        """
        result = await db.execute(
            select(JobPosting).where(JobPosting.is_active == True)
        )
        jobs = result.scalars().all()

        # Group by identity key
        by_key: dict[str, list[JobPosting]] = {}
        for job in jobs:
            by_key.setdefault(job.job_identity_key, []).append(job)

        repost_pairs = 0
        for key, group in by_key.items():
            if len(group) > 1:
                # Sort by first seen
                group.sort(key=lambda j: j.date_first_seen)
                for i, job in enumerate(group[1:], 1):
                    job.repost_count = i
                    repost_pairs += 1

        await db.flush()
        return {"identity_keys_processed": len(by_key), "repost_pairs_found": repost_pairs}

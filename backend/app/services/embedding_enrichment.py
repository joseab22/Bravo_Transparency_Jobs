"""Optional batch generation of description embeddings."""
from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import JobEmbedding, JobPosting
from app.services.repost_detector import embed_text


async def enrich_embeddings(db: AsyncSession, limit: int | None = None) -> dict:
    if not settings.description_embeddings_enabled:
        return {"status": "disabled", "created": 0}
    batch = limit or settings.embedding_batch_size
    jobs = list((await db.execute(
        select(JobPosting)
        .outerjoin(JobEmbedding, JobEmbedding.job_posting_id == JobPosting.id)
        .where(JobEmbedding.id.is_(None), JobPosting.description_raw.is_not(None))
        .limit(batch)
    )).scalars())
    created = errors = 0
    for job in jobs:
        try:
            vector = await asyncio.to_thread(embed_text, job.description_raw[:4000])
            db.add(JobEmbedding(job_posting_id=job.id, vector=vector, model_name=settings.embedding_model))
            created += 1
        except Exception:
            errors += 1
    await db.commit()
    return {"status": "completed", "created": created, "errors": errors}

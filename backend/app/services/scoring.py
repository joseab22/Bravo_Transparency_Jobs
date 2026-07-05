"""Hiring transparency scoring derived from observed posting history."""
from __future__ import annotations

from statistics import mean
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Company, JobPosting, JobSnapshot, SalaryBenchmark
from app.services.normalizer import calculate_days_active


class ScoringService:
    async def score_job(self, job: JobPosting, db: AsyncSession) -> dict:
        job.days_active = calculate_days_active(job.date_posted, job.date_first_seen)
        ghost, confidence = await self._ghost_probability(job, db)
        activity = await self._activity_score(job, db)
        active_hiring = self._active_hiring_confidence(job, ghost, activity, confidence)
        salary_fairness, market_salary = await self._salary_fairness(job, db)
        stability = await self._stability(job, db)
        description_change = await self._description_change(job, db)
        applicant_trend = await self._applicant_trend(job, db)
        salary_trend = await self._salary_trend(job, db)
        competition = min(100.0, 20.0 + (job.applicant_count or 0) / 10.0)

        scores = {
            "ghost_job_probability": round(ghost, 3),
            "ghost_confidence": round(confidence, 3),
            "health_score": round(100 * (1 - ghost), 1),
            "competition_score": round(competition, 1),
            "interview_opportunity_score": round(max(0.0, active_hiring - competition * 0.25), 1),
            "salary_fairness_score": round(salary_fairness, 1) if salary_fairness is not None else None,
            "market_salary": market_salary,
            "stability_score": round(stability, 1),
            "activity_score": round(activity, 1),
            "active_hiring_confidence": round(active_hiring, 1),
            "description_change_score": round(description_change, 1),
            "applicant_trend": round(applicant_trend, 3) if applicant_trend is not None else None,
            "salary_trend": round(salary_trend, 3) if salary_trend is not None else None,
        }
        for key, value in scores.items():
            setattr(job, key, value)
        await db.flush()
        return scores

    async def _ghost_probability(self, job: JobPosting, db: AsyncSession) -> tuple[float, float]:
        features: list[tuple[float, float]] = []
        rc = job.repost_count or 0
        repost_score = 0.05 if rc == 0 else 0.30 if rc <= 2 else 0.65 if rc <= 5 else 0.90
        if job.listing_classification == "parallel":
            repost_score = min(repost_score, 0.10)
        elif job.listing_classification == "repost":
            repost_score = max(repost_score, 0.45)
        features.append((repost_score, settings.ghost_job_repost_weight))

        da = job.days_active or 0
        days_score = 0.05 if da <= 14 else 0.20 if da <= 45 else 0.45 if da <= 90 else 0.75 if da <= 180 else 0.90
        features.append((days_score, settings.ghost_job_days_active_weight))

        if job.applicant_count is not None:
            ac = job.applicant_count
            features.append((0.05 if ac <= 50 else 0.25 if ac <= 250 else 0.55 if ac <= 750 else 0.80, settings.ghost_job_applicants_weight))

        features.append((0.15 if job.salary_listed else 0.60, settings.ghost_job_salary_weight))
        if job.company and job.company.glassdoor_rating is not None:
            rating = job.company.glassdoor_rating
            features.append((0.10 if rating >= 4 else 0.35 if rating >= 3 else 0.65, settings.ghost_job_rating_weight))

        siblings = await db.scalar(
            select(func.count(JobPosting.id)).where(
                JobPosting.company_id == job.company_id,
                JobPosting.identity_fingerprint == job.identity_fingerprint,
                JobPosting.id != job.id,
            )
        ) or 0
        history_score = min(0.10 + siblings * 0.08, 0.85)
        features.append((history_score, settings.ghost_job_history_weight))

        weight = sum(item[1] for item in features)
        probability = sum(score * w for score, w in features) / weight if weight else 0.5

        # Confidence reflects independent observations, not merely the number of
        # scoring rules available. A newly collected posting should remain
        # lower-confidence until it is observed again or gains corroborating data.
        confidence = 0.20
        confidence += min(len(job.snapshots), 4) * 0.12
        confidence += 0.10 if job.applicant_count is not None else 0.0
        confidence += 0.08 if job.salary_listed else 0.0
        confidence += 0.08 if job.company and job.company.glassdoor_rating is not None else 0.0
        confidence += min(siblings, 3) * 0.06
        confidence = min(1.0, confidence)
        return max(0.0, min(probability, 1.0)), confidence

    async def _activity_score(self, job: JobPosting, db: AsyncSession) -> float:
        canonical = job.canonical_job_id or job.id
        active_siblings = await db.scalar(
            select(func.count(JobPosting.id)).where(
                JobPosting.is_active.is_(True),
                func.coalesce(JobPosting.canonical_job_id, JobPosting.id) == canonical,
            )
        ) or 1
        recency = max(0.0, 100.0 - min(job.days_active or 0, 120) * 0.65)
        sibling_signal = min(active_siblings * 8.0, 24.0)
        snapshot_signal = min(len(job.snapshots) * 4.0, 16.0)
        return min(100.0, recency * 0.65 + sibling_signal + snapshot_signal)

    @staticmethod
    def _active_hiring_confidence(job: JobPosting, ghost: float, activity: float, data_confidence: float) -> float:
        score = (1 - ghost) * 60 + activity * 0.30 + data_confidence * 10
        if job.listing_classification == "parallel":
            score += 5
        elif job.listing_classification == "repost":
            score -= 8
        if not job.is_active:
            score -= 25
        return max(0.0, min(score, 100.0))

    async def _salary_fairness(self, job: JobPosting, db: AsyncSession) -> tuple[Optional[float], Optional[int]]:
        result = await db.execute(
            select(SalaryBenchmark).where(
                SalaryBenchmark.title_normalized == job.title_normalized,
                SalaryBenchmark.seniority == job.seniority,
            ).order_by((SalaryBenchmark.metro_area == job.metro_area).desc()).limit(1)
        )
        benchmark = result.scalar_one_or_none()
        if not benchmark:
            return None, None
        if not job.salary_listed or (job.salary_min is None and job.salary_max is None):
            return None, benchmark.salary_p50
        midpoint = mean([value for value in (job.salary_min, job.salary_max) if value is not None])
        fairness = 50 + ((midpoint - benchmark.salary_p50) / max(benchmark.salary_p50, 1)) * 100
        return max(0.0, min(fairness, 100.0)), benchmark.salary_p50

    async def _stability(self, job: JobPosting, db: AsyncSession) -> float:
        rows = await db.execute(
            select(JobSnapshot.description_hash, JobSnapshot.salary_min, JobSnapshot.salary_max)
            .where(JobSnapshot.job_posting_id == job.id)
            .order_by(JobSnapshot.snapshot_at)
        )
        values = rows.all()
        if len(values) < 2:
            return 70.0
        changes = sum(values[i] != values[i - 1] for i in range(1, len(values)))
        return max(0.0, 100.0 - changes / max(len(values) - 1, 1) * 70.0)

    async def _description_change(self, job: JobPosting, db: AsyncSession) -> float:
        rows = await db.execute(select(JobSnapshot.description_hash).where(JobSnapshot.job_posting_id == job.id).order_by(JobSnapshot.snapshot_at))
        hashes = [row[0] for row in rows.all() if row[0]]
        return 0.0 if len(hashes) < 2 else min(100.0, (len(set(hashes)) - 1) / (len(hashes) - 1) * 100)

    async def _applicant_trend(self, job: JobPosting, db: AsyncSession) -> Optional[float]:
        rows = await db.execute(select(JobSnapshot.applicant_count).where(JobSnapshot.job_posting_id == job.id, JobSnapshot.applicant_count.is_not(None)).order_by(JobSnapshot.snapshot_at))
        counts = [row[0] for row in rows.all()]
        return None if len(counts) < 2 else mean([counts[i] - counts[i - 1] for i in range(1, len(counts))])

    async def _salary_trend(self, job: JobPosting, db: AsyncSession) -> Optional[float]:
        rows = await db.execute(select(JobSnapshot.salary_min, JobSnapshot.salary_max).where(JobSnapshot.job_posting_id == job.id).order_by(JobSnapshot.snapshot_at))
        mids = [mean([v for v in row if v is not None]) for row in rows.all() if any(v is not None for v in row)]
        return None if len(mids) < 2 else mean([mids[i] - mids[i - 1] for i in range(1, len(mids))])

    async def update_company_metrics(self, db: AsyncSession) -> int:
        companies = list((await db.execute(select(Company))).scalars())
        updated = 0
        for company in companies:
            jobs = list((await db.execute(select(JobPosting).where(
                JobPosting.company_id == company.id,
                JobPosting.is_active.is_(True),
                JobPosting.active_hiring_confidence.is_not(None),
            ))).scalars())
            if not jobs:
                continue
            company.hiring_intensity = mean(j.active_hiring_confidence for j in jobs if j.active_hiring_confidence is not None)
            company.ghost_job_rate = mean(j.ghost_job_probability for j in jobs if j.ghost_job_probability is not None)
            company.avg_reposts = mean(j.repost_count or 0 for j in jobs)
            updated += 1
        await db.flush()
        return updated

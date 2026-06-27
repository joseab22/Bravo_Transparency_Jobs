"""
Scoring service — computes all transparency scores per job posting.

Scores computed:
  ghost_job_probability   0–1
  ghost_confidence        0–1   (data completeness)
  health_score            0–100
  competition_score       0–100 (higher = more competitive)
  interview_opportunity_score  0–100
  salary_fairness_score   0–100
  market_salary           int (p50 benchmark)
  stability_score         0–100
  activity_score          0–100 (hiring activity signal)
  description_change_score 0–100 (how much description has drifted)
  applicant_trend         float (slope: positive = growing)
  salary_trend            float (direction: positive = rising)
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.models import JobPosting, RepostEvent, SalaryBenchmark, JobSnapshot
from app.core.config import settings


class ScoringService:

    async def score_job(self, job: JobPosting, db: AsyncSession) -> dict:
        ghost_prob, ghost_conf = await self._ghost_probability(job, db)
        health = self._health_score(job, ghost_prob)
        competition = self._competition_score(job)
        interview = self._interview_score(job, ghost_prob)
        salary_fairness, market_salary = await self._salary_fairness(job, db)
        stability = await self._stability_score(job, db)
        activity = self._activity_score(job)
        desc_change = await self._description_change_score(job, db)
        app_trend = await self._applicant_trend(job, db)
        sal_trend = await self._salary_trend(job, db)

        scores = {
            "ghost_job_probability": round(ghost_prob, 3),
            "ghost_confidence": round(ghost_conf, 3),
            "health_score": round(health, 1),
            "competition_score": round(competition, 1),
            "interview_opportunity_score": round(interview, 1),
            "salary_fairness_score": round(salary_fairness, 1) if salary_fairness is not None else None,
            "market_salary": market_salary,
            "stability_score": round(stability, 1),
            "activity_score": round(activity, 1),
            "description_change_score": round(desc_change, 1),
            "applicant_trend": round(app_trend, 3) if app_trend is not None else None,
            "salary_trend": round(sal_trend, 3) if sal_trend is not None else None,
        }

        for k, v in scores.items():
            setattr(job, k, v)
        await db.flush()
        return scores

    # -------------------------------------------------------------------------
    # Ghost probability
    # -------------------------------------------------------------------------

    async def _ghost_probability(self, job: JobPosting, db: AsyncSession) -> tuple[float, float]:
        w = settings
        feature_scores: dict[str, float] = {}
        feature_weights: dict[str, float] = {}
        data_points = 0

        # Repost count (0.30)
        rc = job.repost_count or 0
        feature_scores["repost"] = (
            0.05 if rc == 0 else 0.25 if rc <= 2 else
            0.55 if rc <= 5 else 0.80 if rc <= 10 else 0.95
        )
        feature_weights["repost"] = w.ghost_job_repost_weight
        data_points += 1

        # Days active (0.25)
        da = job.days_active or 0
        feature_scores["days"] = (
            0.05 if da <= 7 else 0.15 if da <= 30 else
            0.35 if da <= 60 else 0.60 if da <= 120 else 0.90
        )
        feature_weights["days"] = w.ghost_job_days_active_weight
        data_points += 1

        # Applicant count (0.15)
        if job.applicant_count is not None:
            ac = job.applicant_count
            feature_scores["applicants"] = (
                0.05 if ac <= 50 else 0.20 if ac <= 200 else
                0.45 if ac <= 500 else 0.70 if ac <= 1000 else 0.90
            )
            feature_weights["applicants"] = w.ghost_job_applicants_weight
            data_points += 1

        # Salary listed (0.10)
        feature_scores["salary"] = 0.15 if job.salary_listed else 0.65
        feature_weights["salary"] = w.ghost_job_salary_weight
        data_points += 1

        # Company rating (0.10)
        if job.company and job.company.glassdoor_rating is not None:
            r = job.company.glassdoor_rating
            feature_scores["rating"] = (
                0.10 if r >= 4.0 else 0.35 if r >= 3.0 else 0.60 if r >= 2.0 else 0.80
            )
            feature_weights["rating"] = w.ghost_job_rating_weight
            data_points += 1

        # Historical repost count (0.10)
        hist = await self._count_historical_reposts(job, db)
        feature_scores["history"] = (
            0.85 if hist > 10 else 0.60 if hist > 5 else 0.35 if hist > 2 else 0.10
        )
        feature_weights["history"] = w.ghost_job_history_weight
        data_points += 1

        total_w = sum(feature_weights[k] for k in feature_scores)
        if total_w == 0:
            return 0.5, 0.0
        prob = sum(feature_scores[k] * feature_weights[k] for k in feature_scores) / total_w
        confidence = data_points / 6
        return min(prob, 0.99), confidence

    async def _count_historical_reposts(self, job: JobPosting, db: AsyncSession) -> int:
        r = await db.execute(
            select(func.count(RepostEvent.id)).where(
                RepostEvent.job_identity_key == job.job_identity_key
            )
        )
        return r.scalar_one() or 0

    # -------------------------------------------------------------------------
    # Derived scores
    # -------------------------------------------------------------------------

    def _health_score(self, job: JobPosting, ghost_prob: float) -> float:
        base = (1 - ghost_prob) * 70
        if job.salary_listed:
            base += 10
        if job.days_active <= 7:
            base += 10
        elif job.days_active <= 30:
            base += 5
        if job.applicant_count:
            base += 10 if job.applicant_count < 100 else 5 if job.applicant_count < 300 else 0
        return min(base, 100.0)

    def _competition_score(self, job: JobPosting) -> float:
        ac = job.applicant_count
        if not ac:
            return 50.0
        return (
            15.0 if ac <= 25 else 30.0 if ac <= 75 else 50.0 if ac <= 200 else
            70.0 if ac <= 500 else 85.0 if ac <= 1000 else 95.0
        )

    def _interview_score(self, job: JobPosting, ghost_prob: float) -> float:
        base = (1 - ghost_prob) * 80
        if job.days_active and job.days_active <= 14:
            base += 15
        if job.repost_count == 0:
            base += 5
        return min(base, 100.0)

    def _activity_score(self, job: JobPosting) -> float:
        """Hiring activity proxy: fast + low repost + salary listed = high activity."""
        base = 50.0
        if job.days_active <= 7:
            base += 30
        elif job.days_active <= 14:
            base += 20
        elif job.days_active <= 30:
            base += 10
        elif job.days_active > 90:
            base -= 20
        if job.repost_count == 0:
            base += 10
        elif job.repost_count > 5:
            base -= 15
        if job.salary_listed:
            base += 10
        return max(0.0, min(100.0, base))

    async def _salary_fairness(self, job: JobPosting, db: AsyncSession) -> tuple[Optional[float], Optional[int]]:
        if not job.salary_min and not job.salary_max:
            return None, None
        r = await db.execute(
            select(SalaryBenchmark).where(
                and_(SalaryBenchmark.title_normalized == job.title_normalized,
                     SalaryBenchmark.metro_area == job.metro_area)
            )
        )
        benchmark = r.scalar_one_or_none()
        if not benchmark:
            r = await db.execute(
                select(SalaryBenchmark).where(SalaryBenchmark.title_normalized == job.title_normalized)
            )
            benchmark = r.scalar_one_or_none()
        if not benchmark:
            return None, None
        job_mid = ((job.salary_min or 0) + (job.salary_max or 0)) / 2
        market = benchmark.salary_p50
        ratio = job_mid / market if market else 1.0
        score = (
            95.0 if ratio >= 1.10 else 80.0 if ratio >= 0.95 else
            65.0 if ratio >= 0.85 else 45.0 if ratio >= 0.75 else
            25.0 if ratio >= 0.65 else 10.0
        )
        return score, market

    async def _stability_score(self, job: JobPosting, db: AsyncSession) -> float:
        base = 50.0
        company = job.company
        if not company:
            return base
        if company.glassdoor_rating:
            base += (company.glassdoor_rating - 3.0) * 15
        if company.ghost_job_rate is not None:
            base -= company.ghost_job_rate * 30
        if company.avg_reposts is not None:
            base += 10 if company.avg_reposts <= 1 else -15 if company.avg_reposts >= 5 else 0
        return max(0.0, min(100.0, base))

    async def _description_change_score(self, job: JobPosting, db: AsyncSession) -> float:
        """Higher = more description changes = more suspicious."""
        r = await db.execute(
            select(JobSnapshot.description_hash)
            .where(JobSnapshot.job_posting_id == job.id)
            .order_by(JobSnapshot.snapshot_at)
        )
        hashes = [row[0] for row in r.fetchall() if row[0]]
        if len(hashes) < 2:
            return 0.0
        unique = len(set(hashes))
        change_rate = (unique - 1) / (len(hashes) - 1)
        return min(change_rate * 100, 100.0)

    async def _applicant_trend(self, job: JobPosting, db: AsyncSession) -> Optional[float]:
        """Slope of applicant count over snapshots (positive = growing)."""
        r = await db.execute(
            select(JobSnapshot.applicant_count)
            .where(and_(
                JobSnapshot.job_posting_id == job.id,
                JobSnapshot.applicant_count != None,
            ))
            .order_by(JobSnapshot.snapshot_at)
        )
        counts = [row[0] for row in r.fetchall()]
        if len(counts) < 2:
            return None
        diffs = [counts[i+1] - counts[i] for i in range(len(counts)-1)]
        return sum(diffs) / len(diffs)

    async def _salary_trend(self, job: JobPosting, db: AsyncSession) -> Optional[float]:
        """Direction of salary changes across snapshots."""
        r = await db.execute(
            select(
                func.coalesce(JobSnapshot.salary_min, 0),
                func.coalesce(JobSnapshot.salary_max, 0),
            )
            .where(and_(
                JobSnapshot.job_posting_id == job.id,
                JobSnapshot.salary_min != None,
            ))
            .order_by(JobSnapshot.snapshot_at)
        )
        rows = r.fetchall()
        if len(rows) < 2:
            return None
        mids = [(row[0] + row[1]) / 2 for row in rows]
        diffs = [mids[i+1] - mids[i] for i in range(len(mids)-1)]
        return sum(diffs) / len(diffs)

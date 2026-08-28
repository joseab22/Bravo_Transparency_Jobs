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
    def _active_hiring_components(
        job: JobPosting,
        ghost: float,
        activity: float,
        data_confidence: float,
    ) -> dict[str, float]:
        classification = (job.listing_classification or "original").lower()
        return {
            "posting_health": (1.0 - ghost) * 60.0,
            "activity": activity * 0.30,
            "evidence": data_confidence * 10.0,
            "listing_pattern": 5.0 if classification == "parallel" else -8.0 if classification == "repost" else 0.0,
            "availability": 0.0 if job.is_active else -25.0,
        }

    @classmethod
    def _active_hiring_confidence(
        cls,
        job: JobPosting,
        ghost: float,
        activity: float,
        data_confidence: float,
    ) -> float:
        components = cls._active_hiring_components(job, ghost, activity, data_confidence)
        return max(0.0, min(sum(components.values()), 100.0))

    @staticmethod
    def active_hiring_reasoning(job: JobPosting, *, source_count: int | None = None) -> Optional[dict]:
        """Explain an existing Active Hiring Confidence score without rescoring.

        The explanation mirrors ``_active_hiring_confidence`` and translates the
        stored inputs into plain language. It does not create a second score or
        require additional database writes.
        """
        if job.active_hiring_confidence is None:
            return None

        def join_items(items: list[str]) -> str:
            if not items:
                return ""
            if len(items) == 1:
                return items[0]
            if len(items) == 2:
                return f"{items[0]} and {items[1]}"
            return f"{', '.join(items[:-1])}, and {items[-1]}"

        ghost = float(job.ghost_job_probability if job.ghost_job_probability is not None else 0.5)
        activity = float(job.activity_score if job.activity_score is not None else 0.0)
        evidence = float(job.ghost_confidence if job.ghost_confidence is not None else 0.0)
        classification = (job.listing_classification or "original").lower()
        score_components = ScoringService._active_hiring_components(job, ghost, activity, evidence)

        health_points = score_components["posting_health"]
        activity_points = score_components["activity"]
        evidence_points = score_components["evidence"]
        listing_adjustment = score_components["listing_pattern"]
        active_adjustment = score_components["availability"]
        days_active = int(job.days_active or 0)
        risk_percent = ghost * 100
        evidence_percent = evidence * 100
        company_rating = getattr(getattr(job, "company", None), "glassdoor_rating", None)
        present_evidence: list[str] = []
        if job.salary_listed:
            present_evidence.append("salary disclosure")
        if job.applicant_count is not None:
            present_evidence.append("applicant count")
        if company_rating is not None:
            present_evidence.append("company rating")

        if ghost < 0.25:
            health_interpretation = "JobLens found few warning signs associated with stale or repeatedly recycled listings."
        elif ghost < 0.50:
            health_interpretation = "JobLens found some warning signs, but the posting is not in the highest risk range."
        else:
            health_interpretation = "JobLens found several warning signs associated with stale or repeatedly recycled listings."

        if activity >= 75:
            activity_interpretation = "This is a strong signal that the employer may be recruiting now."
        elif activity >= 45:
            activity_interpretation = "There is some current activity, but it is not as strong or consistent as higher scoring postings."
        else:
            activity_interpretation = "Current activity signals are limited, which makes immediate hiring less certain."

        if evidence >= 0.70:
            evidence_interpretation = "The score is supported by several observations or supporting data fields."
        elif evidence >= 0.40:
            evidence_interpretation = "The score has some supporting evidence, but important information is still missing."
        else:
            evidence_interpretation = "The score is based on limited supporting evidence, so it should be treated with more caution."

        components = [
            {
                "key": "posting_health",
                "label": "Posting reliability",
                "points": round(health_points, 1),
                "maximum": 60.0,
                "tone": "positive" if ghost < 0.35 else "negative" if ghost >= 0.60 else "neutral",
                "detail": (
                    f"Estimated stale or recycled listing risk is {risk_percent:.0f}%. {health_interpretation} "
                    + (
                        f"This listing has {job.repost_count} repost{'s' if job.repost_count != 1 else ''} on record."
                        if job.repost_count
                        else "No repost history is recorded for this listing."
                    )
                ),
            },
            {
                "key": "activity",
                "label": "Recent hiring activity",
                "points": round(activity_points, 1),
                "maximum": 30.0,
                "tone": "positive" if activity >= 65 else "negative" if activity < 35 else "neutral",
                "detail": (
                    f"Activity is {activity:.0f}/100. {activity_interpretation} "
                    f"First observed {days_active} day{'s' if days_active != 1 else ''} ago"
                    + (f", found across {source_count} sources." if source_count and source_count > 1 else ".")
                ),
            },
            {
                "key": "evidence",
                "label": "Strength of evidence",
                "points": round(evidence_points, 1),
                "maximum": 10.0,
                "tone": "positive" if evidence >= 0.65 else "negative" if evidence < 0.35 else "neutral",
                "detail": (
                    f"Evidence confidence is {evidence_percent:.0f}%. {evidence_interpretation} "
                    + (
                        f"Supported by {join_items(present_evidence)}."
                        if present_evidence
                        else "No supporting data points (salary, applicant count, or company rating) are available."
                    )
                ),
            },
        ]

        if listing_adjustment:
            components.append({
                "key": "listing_pattern",
                "label": "Listing history",
                "points": listing_adjustment,
                "maximum": None,
                "tone": "positive" if listing_adjustment > 0 else "negative",
                "detail": (
                    "JobLens found multiple active listings that appear to represent separate openings for the same role. "
                    "This adds 5 points because simultaneous openings can indicate team, location, or volume hiring."
                    if listing_adjustment > 0
                    else "The role appeared again after an earlier listing. A repost can mean continued recruiting, but it can also mean "
                    "the opening was recycled or remained unfilled, so 8 points are removed."
                ),
            })

        if active_adjustment:
            components.append({
                "key": "inactive",
                "label": "Current availability",
                "points": active_adjustment,
                "maximum": None,
                "tone": "negative",
                "detail": "JobLens currently marks this listing inactive, so 25 points are removed.",
            })

        signals: list[str] = []
        if not job.is_active:
            signals.append("The listing is currently marked inactive in JobLens.")
        elif days_active <= 14:
            signals.append(f"The role was posted or first observed {days_active} day{'s' if days_active != 1 else ''} ago, which is recent.")
        elif days_active >= 90:
            signals.append(f"The listing has been visible for {days_active} days, which can increase uncertainty if other activity signals are weak.")
        else:
            signals.append(f"The listing has been tracked for {days_active} days and is still marked active.")

        if source_count and source_count > 1:
            signals.append(f"The same role was found in {source_count} source listings, providing cross source support.")
        elif source_count == 1:
            signals.append("The role has been found through one source listing so far.")

        if job.repost_count:
            signals.append(f"JobLens detected {job.repost_count} prior occurrence{'s' if job.repost_count != 1 else ''} of this role.")
        elif classification == "parallel":
            signals.append("Related openings appear to be active at the same time.")
        else:
            signals.append("No repost history is currently recorded.")

        if job.salary_listed:
            signals.append("The employer disclosed compensation in the listing.")
        if job.applicant_count is not None:
            signals.append(f"Reported applicant count: {job.applicant_count:,}.")
        if company_rating is not None:
            signals.append(f"Company rating data is available: {company_rating:.1f}/5.")

        limitations: list[str] = []
        if job.applicant_count is None:
            limitations.append("Applicant count was not available, so it could not support the estimate.")
        if not job.salary_listed:
            limitations.append("Compensation was not listed, reducing the available transparency evidence.")
        if not source_count or source_count <= 1:
            limitations.append("Only one source listing has been observed, so cross source support is limited.")
        limitations.append(
            "The score estimates hiring activity from observable posting behavior. It cannot confirm that the employer is interviewing or will fill the role."
        )

        score = float(job.active_hiring_confidence)
        label = "Higher confidence" if score >= 70 else "Mixed signals" if score >= 45 else "Lower confidence"

        positive_factors: list[str] = []
        if ghost < 0.25:
            positive_factors.append("low estimated stale listing risk")
        if activity >= 75:
            positive_factors.append("strong recent activity")
        if evidence >= 0.70:
            positive_factors.append("strong supporting evidence")
        if classification == "parallel":
            positive_factors.append("multiple related openings")
        if source_count and source_count > 1:
            positive_factors.append("cross source support")

        concern_factors: list[str] = []
        if not job.is_active:
            concern_factors.append("inactive status")
        if classification == "repost":
            concern_factors.append("repost history")
        if ghost >= 0.35:
            concern_factors.append("elevated stale listing risk")
        if activity < 60:
            concern_factors.append("weaker recent activity")
        if evidence < 0.50:
            concern_factors.append("limited supporting evidence")
        if days_active >= 90:
            concern_factors.append("a long-running listing")

        if score >= 85:
            reason = join_items(positive_factors[:3]) or "several positive hiring signals"
            summary = f"Strong signs of active hiring. Positive signals include {reason}."
        elif score >= 70:
            reason = join_items(positive_factors[:2]) or "mostly positive posting and activity signals"
            summary = f"Good signs of active hiring. The strongest signals are {reason}, although some information may still be limited."
        elif score >= 45:
            reason = join_items(concern_factors[:3]) or "incomplete or conflicting evidence"
            summary = f"Some positive signals, but meaningful uncertainty. {reason.capitalize()} reduce confidence in immediate hiring."
        else:
            reason = join_items(concern_factors[:3]) or "limited evidence of current hiring activity"
            summary = f"Limited signs of active hiring. The main concerns are {reason}. Verify the role on the employer's careers page before relying on the listing."

        return {
            "score": round(score, 1),
            "label": label,
            "summary": summary,
            "formula": (
                "Posting reliability contributes up to 60 points, recent activity up to 30, and evidence strength up to 10. "
                "Listing history and inactive status can add or subtract points."
            ),
            "components": components,
            "signals": signals,
            "limitations": limitations,
        }

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
        """Refresh company metrics without issuing one job query per company."""
        aggregate_rows = (await db.execute(
            select(
                JobPosting.company_id,
                func.avg(JobPosting.active_hiring_confidence).label("hiring_intensity"),
                func.avg(JobPosting.ghost_job_probability).label("ghost_job_rate"),
                func.avg(func.coalesce(JobPosting.repost_count, 0)).label("avg_reposts"),
            )
            .where(
                JobPosting.is_active.is_(True),
                JobPosting.active_hiring_confidence.is_not(None),
            )
            .group_by(JobPosting.company_id)
        )).all()

        metrics = {
            row.company_id: (
                float(row.hiring_intensity) if row.hiring_intensity is not None else None,
                float(row.ghost_job_rate) if row.ghost_job_rate is not None else None,
                float(row.avg_reposts) if row.avg_reposts is not None else None,
            )
            for row in aggregate_rows
        }

        companies = list((await db.execute(select(Company))).scalars())
        for company in companies:
            values = metrics.get(company.id)
            if values is None:
                company.hiring_intensity = None
                company.ghost_job_rate = None
                company.avg_reposts = None
                continue
            company.hiring_intensity, company.ghost_job_rate, company.avg_reposts = values

        await db.flush()
        return len(metrics)

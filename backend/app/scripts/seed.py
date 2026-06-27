"""
Seed script.
Populates salary_benchmarks with baseline market data.

Run with:
  docker compose exec backend python -m app.scripts.seed
"""

import asyncio
from app.db.session import AsyncSessionLocal
from app.models.models import SalaryBenchmark


SALARY_BENCHMARKS = [
    # (title_normalized, metro_area, seniority, p25, p50, p75)
    ("data analyst", None, "entry", 55000, 68000, 82000),
    ("data analyst", None, "mid", 70000, 88000, 105000),
    ("data analyst", None, "senior", 95000, 115000, 135000),
    ("data analyst", "Los Angeles, California", "mid", 75000, 92000, 110000),
    ("data analyst", "San Francisco, California", "mid", 90000, 110000, 130000),
    ("data analyst", "New York, New York", "mid", 85000, 105000, 125000),
    ("data scientist", None, "entry", 80000, 100000, 120000),
    ("data scientist", None, "mid", 105000, 130000, 155000),
    ("data scientist", None, "senior", 135000, 165000, 200000),
    ("data engineer", None, "entry", 85000, 105000, 125000),
    ("data engineer", None, "mid", 110000, 135000, 160000),
    ("data engineer", None, "senior", 140000, 170000, 205000),
    ("machine learning engineer", None, "mid", 120000, 150000, 180000),
    ("machine learning engineer", None, "senior", 155000, 190000, 230000),
    ("software engineer", None, "entry", 90000, 115000, 140000),
    ("software engineer", None, "mid", 120000, 150000, 180000),
    ("software engineer", None, "senior", 155000, 195000, 235000),
    ("analytics engineer", None, "mid", 105000, 130000, 155000),
    ("analytics engineer", None, "senior", 130000, 160000, 195000),
    ("product manager", None, "mid", 110000, 140000, 170000),
    ("quantitative analyst", None, "mid", 120000, 155000, 200000),
]


async def seed():
    async with AsyncSessionLocal() as db:
        for title, metro, seniority, p25, p50, p75 in SALARY_BENCHMARKS:
            existing = await db.get(SalaryBenchmark, {"title_normalized": title, "metro_area": metro, "seniority": seniority})
            if existing:
                continue
            benchmark = SalaryBenchmark(
                title_normalized=title,
                metro_area=metro,
                seniority=seniority,
                salary_p25=p25,
                salary_p50=p50,
                salary_p75=p75,
                sample_size=100,
            )
            db.add(benchmark)

        await db.commit()
        print(f"Seeded {len(SALARY_BENCHMARKS)} salary benchmarks.")


if __name__ == "__main__":
    asyncio.run(seed())

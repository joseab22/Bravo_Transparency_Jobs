"""Print JobLens's protected JSearch request-budget status."""
from __future__ import annotations

import asyncio
import json

from app.core.config import settings
from app.services.request_budget import RapidAPIRequestBudget

#Uses legacy terminology of Rapid API, instead of OpenwWeb ninja. 
async def main() -> None:
    budget = RapidAPIRequestBudget(
        settings.redis_url,
        namespace="jsearch",
        monthly_limit=settings.jsearch_monthly_request_limit,
        reserve=settings.jsearch_request_reserve,
    )
    try:
        payload = (await budget.status()).as_dict()
        payload["scheduled_requests_per_run"] = settings.jsearch_requests_per_run
        payload["estimated_scheduled_requests_31_days"] = settings.jsearch_estimated_monthly_requests
        print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        await budget.close()


if __name__ == "__main__":
    asyncio.run(main())

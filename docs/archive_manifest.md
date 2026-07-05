# Archive Manifest

This archive combines the structured-identity implementation and the scraper-reliability patch.

Required files include:

- `backend/migrations/versions/0002_structured_identity.py`
- `backend/app/services/normalizer.py`
- `backend/app/services/repost_detector.py`
- `backend/app/services/scoring.py`
- `backend/app/workers/ingestion.py`
- `backend/app/workers/scrapers/base.py`
- all eight scraper adapters
- `backend/app/workers/celery_app.py`
- `frontend/.eslintrc.json`
- `docs/identity_resolution.md`
- `docs/scraper_reliability.md`
- `docs/validation.md`
- `docs/github_change_summary.md`

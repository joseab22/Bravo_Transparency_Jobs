# Dependency Map

## Backend dependency graph

```
app.main
  └── app.api.routes.jobs
  │     └── app.services.scoring
  │     └── app.models.models
  │     └── app.schemas.jobs
  └── app.api.routes.companies
        └── app.models.models
        └── app.schemas.jobs

app.workers.celery_app
  └── app.workers.scrapers (registry)
  │     ├── scrapers.indeed      → httpx, tenacity, app.services.normalizer
  │     ├── scrapers.linkedin    → httpx, tenacity, app.services.normalizer
  │     ├── scrapers.glassdoor   → httpx, tenacity, app.services.normalizer
  │     ├── scrapers.ziprecruiter→ httpx, tenacity, app.services.normalizer
  │     ├── scrapers.dice        → httpx, tenacity, app.services.normalizer
  │     ├── scrapers.monster     → httpx, tenacity, app.services.normalizer
  │     ├── scrapers.jobright    → httpx, tenacity, app.services.normalizer
  │     └── scrapers.simplify    → httpx, feedparser, app.services.normalizer
  └── app.workers.ingestion
  │     ├── app.models.models
  │     ├── app.services.normalizer
  │     └── app.services.repost_detector → sentence-transformers, sklearn
  └── app.services.scoring
        ├── app.models.models
        └── app.core.config

app.services.normalizer
  └── geopy (geocoding)
  └── re, unicodedata (stdlib)

app.db.session
  └── sqlalchemy[asyncio]
  └── asyncpg
  └── pgvector
```

## Frontend dependency graph

```
pages/index.tsx
  └── lib/api.ts → axios
  └── types/jobs.ts
  └── styles/globals.css → tailwindcss
```

## Infrastructure dependency graph

```
docker-compose.yml
  ├── pgvector/pgvector:pg15 (postgres)
  ├── redis:7-alpine
  ├── Dockerfile.backend
  │     └── python:3.11-slim
  │     └── requirements.txt
  │         ├── fastapi, uvicorn
  │         ├── sqlalchemy, asyncpg, alembic, pgvector
  │         ├── celery, redis
  │         ├── httpx, beautifulsoup4, playwright, tenacity, feedparser
  │         ├── sentence-transformers, scikit-learn, torch
  │         └── geopy, structlog, pydantic-settings
  └── Dockerfile.frontend
        └── node:18-alpine
        └── package.json
            ├── next, react, react-dom
            ├── axios, swr, @tanstack/react-query
            ├── recharts, lucide-react
            └── tailwindcss, typescript
```

## Key env var → feature dependencies

| Feature | Env var(s) required |
|---------|-------------------|
| Indeed scraping | `RAPIDAPI_KEY` |
| LinkedIn scraping | `RAPIDAPI_KEY` (jsearch mode) |
| Glassdoor scraping | `RAPIDAPI_KEY` |
| Monster scraping | `RAPIDAPI_KEY` |
| ZipRecruiter scraping | `ZIPRECRUITER_API_KEY` |
| Dice scraping | None |
| Simplify scraping | None |
| Jobright scraping | `JOBRIGHT_API_KEY` |
| Location accuracy (high) | `GOOGLE_GEOCODING_API_KEY` |
| All scoring | None (runs on existing DB data) |
| Embedding similarity | None (downloads model on startup) |

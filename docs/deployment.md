# Deployment

1. Copy `backend/.env.example` to `backend/.env` and set production secrets.
2. Enable only sources with valid credentials and confirmed terms.
3. Build and start with `docker compose up -d --build`.
4. Confirm `alembic current` reports `0003_location_cache`.
5. Keep geocoding and embeddings disabled until their quotas, caches, and storage requirements are planned.
6. In production, remove development bind mounts and Uvicorn `--reload`, terminate TLS at a reverse proxy, and use managed PostgreSQL/Redis backups.

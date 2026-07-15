# JobLens security patch summary

Updated files:

- `backend/app/main.py`: restricts CORS to configured origins, `GET`, and `OPTIONS`.
- `backend/app/core/config.py`: adds `ADMIN_API_KEY` support.
- `backend/app/core/security.py`: validates `X-Admin-Key` using constant-time comparison.
- `backend/app/api/routes/jobs.py`: validates query lengths, ranges, enum values, page limits, sort directions, and sort columns; protects the score endpoint.
- `frontend/src/pages/index.tsx`: validates third-party external links before rendering them as clickable URLs.
- `frontend/next.config.js`: adds browser security response headers while preserving API rewrites.
- `infrastructure/nginx/nginx.conf`: adds rate limits for public API and administrative operations.
- `backend/.env.example`: documents the required security environment variables and current JSearch schedule controls.
- `docker-compose.yml`: already contained localhost-only frontend/backend bindings, internal-only PostgreSQL/Redis, and `no-new-privileges`.
- Backend and frontend Dockerfiles already ran application processes as non-root users.

Required secret in `backend/.env`:

```env
CORS_ORIGINS=http://localhost:3000
ADMIN_API_KEY=<generate with: openssl rand -hex 32>
```

Do not commit the generated key or place it in a `NEXT_PUBLIC_` variable.

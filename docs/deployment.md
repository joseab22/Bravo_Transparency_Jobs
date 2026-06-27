# Deployment Guide

This guide covers three hosting options — Railway (recommended), Render, and self-hosted VPS.

---

## Option A: Railway + Vercel (Recommended)

Railway hosts the FastAPI backend, Celery workers, Redis, and PostgreSQL.
Vercel hosts the Next.js frontend.

### 1. Set up Railway

1. Go to https://railway.app and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `job-tracker` repo
4. Railway will detect the `docker-compose.yml` — but for production you'll configure services individually:

**Create these Railway services:**

| Service | Config |
|---|---|
| `postgres` | Template: PostgreSQL → add pgvector via plugin |
| `redis` | Template: Redis |
| `backend` | Dockerfile: `infrastructure/docker/Dockerfile.backend`, root: `backend/` |
| `worker` | Same image as backend, start command: `celery -A app.workers.celery_app worker --loglevel=info` |
| `beat` | Same image, start command: `celery -A app.workers.celery_app beat --loglevel=info` |

**Set Railway environment variables for backend/worker/beat:**
```
DATABASE_URL=${{Postgres.DATABASE_URL}}    # Railway injects this automatically
REDIS_URL=${{Redis.REDIS_URL}}             # Auto-injected
SECRET_KEY=<generate with: openssl rand -hex 32>
RAPIDAPI_KEY=<your key>
ENV=production
```

5. After deploy: `railway run alembic upgrade head` to run migrations

### 2. Set up Vercel

1. Go to https://vercel.com and import your repo
2. Set **Root Directory** to `frontend`
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-railway-backend-url.railway.app
   ```
4. Deploy

### Cost
- Railway: ~$5–10/month (Hobby plan)
- Vercel: Free (Hobby plan)

---

## Option B: Render

1. Go to https://render.com
2. Create a **PostgreSQL** database (enable pgvector via Render shell: `CREATE EXTENSION vector;`)
3. Create a **Redis** instance
4. Create a **Web Service** for the backend:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Root directory: `backend`
5. Create **Background Workers** for Celery (same image, different start command)
6. Deploy frontend to Vercel (same as Option A, Step 2)

---

## Option C: Self-hosted VPS (DigitalOcean / Linode)

1. Provision a $12/month Droplet (2 GB RAM minimum — sentence-transformers needs it)
2. Install Docker + Docker Compose
3. Clone your repo, copy `.env.example` to `.env`, fill in values
4. `docker compose -f docker-compose.prod.yml up -d`
5. Set up Nginx as reverse proxy (see `infrastructure/nginx/`)
6. Use Certbot for SSL: `certbot --nginx -d yourdomain.com`

---

## pgvector on Railway / Render

pgvector isn't in vanilla PostgreSQL images. Both Railway and Render support it:

- **Railway**: Use the pgvector plugin from the Railway marketplace
- **Render**: Connect to your DB and run `CREATE EXTENSION IF NOT EXISTS vector;`
- **Self-hosted**: The `docker-compose.yml` already uses `pgvector/pgvector:pg15`

---

## Post-deploy checklist

- [ ] Run `alembic upgrade head` after first deploy
- [ ] Seed salary benchmarks: `python -m app.scripts.seed_salaries`
- [ ] Trigger first scrape: hit `POST /api/v1/admin/scrape/indeed`
- [ ] Verify Celery beat is running (check logs — should fire every 6h)
- [ ] Set up uptime monitoring (UptimeRobot free tier works)

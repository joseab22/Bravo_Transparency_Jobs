from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.routes import jobs, companies


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="JobLens API",
    description="Labor market intelligence — ghost job detection · repost tracking · salary transparency",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(companies.router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.2.0", "sources": [
        "indeed", "linkedin", "glassdoor", "ziprecruiter",
        "dice", "monster", "jobright", "simplify"
    ]}

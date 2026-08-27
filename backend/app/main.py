from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import companies, jobs, user_data
from app.core.config import settings

app = FastAPI(
    title="JobLens API",
    description="Job-market transparency, listing history, and active-hiring confidence.",
    version="0.5.0",
    debug=settings.debug,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-Device-Id"],
)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(companies.router, prefix=settings.api_prefix)
app.include_router(user_data.router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.5.0"}

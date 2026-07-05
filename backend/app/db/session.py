from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base


def _engine_options(database_url: str) -> dict:
    """Use PostgreSQL pooling in production while keeping SQLite tests valid."""
    backend = make_url(database_url).get_backend_name()
    options: dict = {
        "echo": settings.debug,
        "pool_pre_ping": True,
    }
    if backend != "sqlite":
        options.update(pool_size=10, max_overflow=20)
    return options


engine = create_async_engine(settings.database_url, **_engine_options(settings.database_url))
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

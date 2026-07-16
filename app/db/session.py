from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def create_engine_and_sessionmaker(database_url: str | None = None):
    url = database_url or get_settings().database_url
    engine = create_async_engine(url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

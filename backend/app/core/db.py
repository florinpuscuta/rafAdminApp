from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# echo=False: SQL logging se face prin loggerul "sqlalchemy.engine" (controlat în
# core/logging.py). Evităm echo-ul direct care instalează propriul handler și
# produce linii duplicate în formatarea noastră.
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Slow query monitoring — atașăm listener pe engine-ul sync (AsyncEngine
# wrappuiește un sync engine; SQLAlchemy events se atașează acolo).
from app.core.metrics import install_slow_query_listener  # noqa: E402

install_slow_query_listener(engine.sync_engine)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

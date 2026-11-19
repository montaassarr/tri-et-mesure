from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tri_mesure.settings import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


def set_engine(engine: AsyncEngine) -> None:
    """Used by tests to point the app at another database."""
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session

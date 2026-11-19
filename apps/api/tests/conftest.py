"""Test fixtures.

By default the suite runs on in-memory SQLite (fast, no Docker). Set TEST_DATABASE_URL to a
dedicated PostgreSQL database to run exactly the same tests on the production engine
(CI does both). The database named in TEST_DATABASE_URL is wiped.
"""

import os
from collections.abc import AsyncIterator

import pytest

# Tests never call a paid model, never start the background worker, never touch dev data.
os.environ["LLM_PROVIDER"] = "rules"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_COMPAT_API_KEY"] = ""
os.environ["WORKER_ENABLED"] = "false"
os.environ["WORKER_CONCURRENCY"] = "1"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from tri_mesure.application import measurement, sources
from tri_mesure.db.models import Base
from tri_mesure.db.session import get_sessionmaker, set_engine
from tri_mesure.settings import get_settings

get_settings.cache_clear()
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _engine() -> AsyncEngine:
    if TEST_DATABASE_URL:
        return create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = _engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    set_engine(engine)
    async with get_sessionmaker()() as session:
        await measurement.ensure_assumptions(session)
        await sources.ensure_internal_source(session)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    from tri_mesure.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client: AsyncClient, role: str, name: str = "testeur") -> dict[str, str]:
    r = await client.post("/api/auth/demo-login", json={"name": name, "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

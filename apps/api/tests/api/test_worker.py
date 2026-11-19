"""The analysis worker: claiming, retries, failure, and the background loop."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from tri_mesure.application import analysis, intake
from tri_mesure.db.models import AuditEvent, Email, utcnow
from tri_mesure.db.session import get_sessionmaker
from tri_mesure.settings import get_settings


async def _ingest(n: int = 3) -> list[int]:
    async with get_sessionmaker()() as session:
        ids = []
        for i in range(n):
            e = await intake.ingest_email(
                session,
                subject=f"Sinistre {i}",
                body="Je souhaite résilier mon contrat CT12345678.",
                sender_email="x@example.fr",
                received_at=utcnow(),
                external_id=f"t{i}",
            )
            ids.append(e.id)
        await session.commit()
        return ids


async def test_intake_queues_without_calling_the_model(engine: AsyncEngine) -> None:
    await _ingest(2)
    async with get_sessionmaker()() as session:
        statuses = set((await session.execute(select(Email.analysis_status))).scalars())
        assert statuses == {"pending"}
        assert await analysis.queue_depth(session) == 2


async def test_process_pending_analyses_everything_once(engine: AsyncEngine) -> None:
    await _ingest(3)
    assert await analysis.process_pending(get_settings(), get_sessionmaker()) == 3
    assert await analysis.process_pending(get_settings(), get_sessionmaker()) == 0
    async with get_sessionmaker()() as session:
        rows = (await session.execute(select(Email))).scalars().all()
        assert {e.analysis_status for e in rows} == {"done"}
        assert all(e.analysis_attempts == 1 for e in rows)


async def test_failures_are_retried_then_marked_failed(engine: AsyncEngine) -> None:
    [email_id] = await _ingest(1)
    async with get_sessionmaker()() as session:
        e = await session.get_one(Email, email_id)
        e.body_raw = None  # analysis is impossible: simulates a permanent error
        await session.commit()
    settings = get_settings()
    for _ in range(settings.worker_max_attempts):
        await analysis.process_pending(settings, get_sessionmaker())
    async with get_sessionmaker()() as session:
        e = await session.get_one(Email, email_id)
        assert e.analysis_status == "failed"
        assert e.analysis_attempts == settings.worker_max_attempts
        failed = (
            (await session.execute(select(AuditEvent).where(AuditEvent.type == "ai.failed")))
            .scalars()
            .all()
        )
        assert len(failed) == 1 and failed[0].actor == "system:worker"


async def test_background_loop_drains_the_queue(engine: AsyncEngine) -> None:
    await _ingest(2)
    settings = get_settings().model_copy(update={"worker_poll_seconds": 0.05})
    worker = analysis.AnalysisWorker(settings, get_sessionmaker())
    worker.start()
    try:
        # Wait on the worker's own progress: the in-memory SQLite test database has a single
        # connection, so the test must not query it while the worker is writing.
        for _ in range(200):
            if worker.processed_total >= 2:
                break
            await asyncio.sleep(0.05)
    finally:
        await worker.stop()
    assert not worker.running and worker.processed_total == 2
    async with get_sessionmaker()() as session:
        assert await analysis.queue_depth(session) == 0


async def test_stop_is_graceful_and_fast_when_idle(engine: AsyncEngine) -> None:
    settings = get_settings().model_copy(update={"worker_poll_seconds": 30})
    worker = analysis.AnalysisWorker(settings, get_sessionmaker())
    worker.start()
    await asyncio.sleep(0.1)  # now sleeping for up to 30 s between polls
    started = asyncio.get_running_loop().time()
    await worker.stop()
    assert asyncio.get_running_loop().time() - started < 2  # woke up, did not wait 30 s
    assert not worker.running

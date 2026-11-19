"""Asynchronous AI analysis.

Intake marks e-mails `pending`. The worker claims a batch, runs the pipeline (mask -> model
-> rules) and stores the suggestion. Claiming uses `FOR UPDATE SKIP LOCKED` on PostgreSQL,
so several workers (or API replicas) can run side by side without analysing an e-mail
twice. A `running` e-mail whose worker died is picked up again after STALE_AFTER.

State machine:  pending --claim--> running --ok--> done
                                     |--error--> pending (retry) | failed (max attempts)
"""

import asyncio
import contextlib
from datetime import timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from tri_mesure.application.ai_config import build_gateway, effective_config
from tri_mesure.audit.store import append_event
from tri_mesure.db.models import Email, LLMCall, Suggestion, utcnow
from tri_mesure.llm.gateway import Gateway
from tri_mesure.observability import ANALYSIS_QUEUE, LLM_CALLS, LLM_COST_EUR, LLM_LATENCY, log
from tri_mesure.pipeline import suggest as run_pipeline
from tri_mesure.settings import Settings

STALE_AFTER = timedelta(minutes=5)
WORKER_ACTOR = "system:worker"


async def analyze_email(session: AsyncSession, email: Email, gateway: Gateway) -> Suggestion:
    """Run the pipeline for one e-mail and persist the ledger rows and the suggestion."""
    if email.body_raw is None:
        raise ValueError("Texte original purgé : nouvelle analyse impossible")
    s = await run_pipeline(gateway, email.subject, email.body_raw, email.received_at.date())
    extraction = s.outcome.extraction
    assert extraction is not None  # the rules fallback always answers

    calls: list[LLMCall] = []
    for attempt in s.outcome.attempts:
        r = attempt.result
        outcome = "ok" if r.schema_valid else ("error" if r.error else "invalid")
        LLM_CALLS.labels(r.provider, r.model, outcome).inc()
        LLM_LATENCY.labels(r.provider).observe(r.latency_ms / 1000)
        if attempt.cost_eur:
            LLM_COST_EUR.labels(r.model).inc(attempt.cost_eur)
        call = LLMCall(
            email_id=email.id,
            gen_ai_system=r.provider,
            gen_ai_request_model=r.model,
            prompt_version=attempt.prompt_version,
            gen_ai_usage_input_tokens=r.usage.input_tokens,
            gen_ai_usage_output_tokens=r.usage.output_tokens,
            cache_read_tokens=r.usage.cache_read_tokens,
            cache_write_tokens=r.usage.cache_write_tokens,
            cost_eur=attempt.cost_eur,
            latency_ms=r.latency_ms,
            schema_valid=r.schema_valid,
            stop_reason=r.stop_reason,
            error=(r.error or "")[:500] or None,
            masked_prompt=f"{gateway.system}\n\n=== USER ===\n"
            f"Objet : {s.masked.subject}\n{s.masked.body}",
        )
        session.add(call)
        calls.append(call)
    await session.flush()

    final = s.outcome.final
    suggestion = Suggestion(
        email_id=email.id,
        llm_call_id=calls[-1].id,
        source="interne",
        latency_ms=sum(a.result.latency_ms for a in s.outcome.attempts),
        provider=final.result.provider,
        model=final.result.model,
        prompt_version=final.prompt_version,
        category=extraction.category,
        sender_type=extraction.sender_type,
        confidence=extraction.confidence,
        fields=s.fields,
        spans=s.spans,
        summary=extraction.summary,
        priority=s.priority.priority,
        priority_reasons=s.priority.reasons,
        needs_manual=s.needs_manual,
        manual_reason=s.manual_reason,
        used_fallback=s.outcome.used_fallback,
        cost_eur=s.outcome.total_cost_eur,
    )
    session.add(suggestion)
    await session.flush()
    await append_event(
        session,
        "ai.suggested",
        f"ai:{final.result.model}",
        {
            "suggestion_id": suggestion.id,
            "provider": final.result.provider,
            "model": final.result.model,
            "prompt_version": final.prompt_version,
            "category": extraction.category,
            "confidence": extraction.confidence,
            "attempts": len(s.outcome.attempts),
            "used_fallback": s.outcome.used_fallback,
            "input_tokens": sum(a.result.usage.input_tokens for a in s.outcome.attempts),
            "output_tokens": sum(a.result.usage.output_tokens for a in s.outcome.attempts),
            "cost_eur": round(s.outcome.total_cost_eur, 8),
        },
        email.id,
    )
    await append_event(
        session,
        "priority.computed",
        "system:rules",
        {"priority": s.priority.priority, "reasons": s.priority.reasons},
        email.id,
    )
    return suggestion


async def claim_batch(session: AsyncSession, limit: int) -> list[int]:
    now = utcnow()
    query = (
        select(Email.id)
        .where(
            or_(
                Email.analysis_status == "pending",
                and_(
                    Email.analysis_status == "running",
                    Email.analysis_started_at < now - STALE_AFTER,
                ),
            )
        )
        .order_by(Email.queued_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    ids = list((await session.execute(query)).scalars())
    if ids:
        await session.execute(
            update(Email)
            .where(Email.id.in_(ids))
            .values(
                analysis_status="running",
                analysis_started_at=now,
                analysis_attempts=Email.analysis_attempts + 1,
            )
        )
    await session.commit()
    return ids


async def _process_one(
    email_id: int, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> bool:
    async with sessionmaker() as session:
        email = (
            await session.execute(
                select(Email).where(Email.id == email_id).options(selectinload(Email.suggestions))
            )
        ).scalar_one()
        try:
            config = await effective_config(session, settings)
            await analyze_email(session, email, build_gateway(session, settings, config))
            email.analysis_status = "done"
            email.analysis_error = None
            await session.commit()
            return True
        except Exception as e:  # the worker must survive any single failure
            await session.rollback()
            email = await session.get_one(Email, email_id)
            final = email.analysis_attempts >= settings.worker_max_attempts
            email.analysis_status = "failed" if final else "pending"
            email.analysis_error = f"{type(e).__name__}: {e}"[:300]
            if final:
                await append_event(
                    session,
                    "ai.failed",
                    WORKER_ACTOR,
                    {"attempts": email.analysis_attempts, "error": email.analysis_error},
                    email.id,
                )
            await session.commit()
            log.warning("analysis_failed", email_id=email_id, final=final, error=str(e)[:200])
            return False


async def process_pending(
    settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], max_items: int = 1000
) -> int:
    """Drain the queue (up to max_items). Returns the number of e-mails processed."""
    processed = 0
    sem = asyncio.Semaphore(max(1, settings.worker_concurrency))
    while processed < max_items:
        async with sessionmaker() as session:
            ids = await claim_batch(session, min(settings.worker_concurrency * 2, max_items))
        if not ids:
            break

        async def run(i: int) -> None:
            async with sem:
                await _process_one(i, settings, sessionmaker)

        await asyncio.gather(*(run(i) for i in ids))
        processed += len(ids)
    return processed


async def queue_depth(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Email)
                .where(Email.analysis_status.in_(("pending", "running")))
            )
        ).scalar_one()
    )


async def request_reanalysis(session: AsyncSession, actor: str) -> int:
    """Send every open, not-yet-reviewed case back to the worker (after a config change)."""
    result = await session.execute(
        update(Email)
        .where(Email.status == "nouveau", Email.analysis_status.in_(("done", "failed")))
        .values(analysis_status="pending", analysis_attempts=0, analysis_error=None)
    )
    count = int(getattr(result, "rowcount", 0) or 0)
    await append_event(session, "ai.reanalysis_requested", actor, {"count": count})
    await session.commit()
    return count


class AnalysisWorker:
    """Background loop started with the API (can also run as a separate process).

    Graceful shutdown: `stop()` asks the loop to finish its current batch and exit; it only
    cancels if that takes longer than `shutdown_timeout`. A batch is therefore never cut in
    the middle of a database write during a normal deploy or restart.
    """

    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        shutdown_timeout: float = 30.0,
    ):
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.shutdown_timeout = shutdown_timeout
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self.last_error: str | None = None
        self.processed_total = 0  # observable progress (health, tests)

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self.running:
            self._stopping.clear()
            self._task = asyncio.create_task(self._loop(), name="analysis-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopping.set()
        try:
            await asyncio.wait_for(asyncio.shield(self._task), self.shutdown_timeout)
        except TimeoutError:
            log.warning("worker_forced_stop", timeout_s=self.shutdown_timeout)
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        log.info("worker_stopped", processed_total=self.processed_total)

    async def _pause(self, seconds: float) -> None:
        """Sleep, but wake up immediately when a stop is requested."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), seconds)

    async def _loop(self) -> None:
        log.info("worker_started", concurrency=self.settings.worker_concurrency)
        while not self._stopping.is_set():
            try:
                done = await process_pending(self.settings, self.sessionmaker, max_items=50)
                self.processed_total += done
                async with self.sessionmaker() as session:
                    ANALYSIS_QUEUE.set(await queue_depth(session))
                self.last_error = None
                if done == 0:
                    await self._pause(self.settings.worker_poll_seconds)
            except Exception as e:  # database briefly unavailable, etc.
                self.last_error = f"{type(e).__name__}: {e}"[:200]
                log.error("worker_loop_error", error=self.last_error)
                await self._pause(5)

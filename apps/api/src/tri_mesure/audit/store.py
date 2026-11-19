"""Write and verify audit events in the database."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tri_mesure.audit.chain import GENESIS_HASH, ChainReport, event_content, event_hash, verify
from tri_mesure.db.models import AuditEvent

_LOCK_KEY = 732_001  # arbitrary advisory-lock id serialising chain appends


async def append_event(
    session: AsyncSession,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    email_id: int | None = None,
) -> AuditEvent:
    """Append one event to the chain. Caller commits."""
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    last = (
        await session.execute(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    ).scalar_one_or_none()
    seq = (last.seq + 1) if last else 1
    prev_hash = last.hash if last else GENESIS_HASH
    ts = datetime.now(UTC).isoformat(timespec="milliseconds")
    content = event_content(seq, ts, actor, event_type, email_id, payload)
    event = AuditEvent(
        seq=seq,
        ts=ts,
        actor=actor,
        type=event_type,
        email_id=email_id,
        payload=payload,
        prev_hash=prev_hash,
        hash=event_hash(prev_hash, content),
    )
    session.add(event)
    await session.flush()
    return event


async def verify_chain(session: AsyncSession) -> ChainReport:
    rows = (await session.execute(select(AuditEvent).order_by(AuditEvent.seq))).scalars()
    return verify(
        (event_content(e.seq, e.ts, e.actor, e.type, e.email_id, e.payload), e.prev_hash, e.hash)
        for e in rows
    )


async def list_events(
    session: AsyncSession,
    *,
    email_id: int | None = None,
    event_type: str | None = None,
    actor_prefix: str | None = None,
    before_seq: int | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    """Newest first. Keyset pagination: pass the smallest `seq` you received as `before_seq`."""
    query = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)
    if email_id is not None:
        query = query.where(AuditEvent.email_id == email_id)
    if event_type:
        query = query.where(AuditEvent.type == event_type)
    if actor_prefix:
        query = query.where(AuditEvent.actor.startswith(f"{actor_prefix}:"))
    if before_seq is not None:
        query = query.where(AuditEvent.seq < before_seq)
    return list((await session.execute(query)).scalars())

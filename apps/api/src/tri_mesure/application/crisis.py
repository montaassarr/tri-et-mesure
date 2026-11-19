"""Storm mode: a declared climate event floods the queue; the team lead follows it live.

In real life the e-mails would arrive from the mailbox. Here `start_event` simulates the
burst with synthetic, labelled e-mails. Everything else (masking, analysis, priority,
lease, measurement) is the normal path: storm mode is a load test of the real system.
"""

import random
import statistics
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tri_mesure.application.casework import case_sla
from tri_mesure.application.errors import Conflict, Invalid, NotFound
from tri_mesure.application.intake import ingest_email
from tri_mesure.application.sources import get_champion
from tri_mesure.audit.store import append_event
from tri_mesure.datagen.generate import generate_storm
from tri_mesure.db.models import CrisisEvent, Email, utcnow

KINDS = {"grele": "Grêle", "tempete": "Tempête", "inondation": "Inondation"}
MAX_VOLUME = 400


async def active_event(session: AsyncSession) -> CrisisEvent | None:
    return (
        await session.execute(
            select(CrisisEvent)
            .where(CrisisEvent.ended_at.is_(None))
            .order_by(CrisisEvent.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def start_event(
    session: AsyncSession, name: str, kind: str, volume: int, actor: str
) -> CrisisEvent:
    if kind not in KINDS:
        raise Invalid(f"Type d'événement inconnu : {kind}")
    if not 1 <= volume <= MAX_VOLUME:
        raise Invalid(f"Volume entre 1 et {MAX_VOLUME}")
    if await active_event(session) is not None:
        raise Conflict("Un événement est déjà en cours : clôturez-le d'abord")

    now = utcnow()
    event = CrisisEvent(
        name=name.strip(), kind=kind, volume=volume, created_by=actor, started_at=now
    )
    session.add(event)
    await session.flush()
    await append_event(
        session,
        "crisis.started",
        actor,
        {"event_id": event.id, "name": event.name, "kind": kind, "volume": volume},
    )

    seed = random.SystemRandom().randint(1, 10**9)  # a new storm each time
    for i, sample in enumerate(generate_storm(volume, seed, kind, now.date())):
        email = await ingest_email(
            session,
            subject=sample.subject,
            body=sample.body,
            sender_email=sample.sender_email,
            received_at=now - timedelta(minutes=volume - i),
            external_id=f"evt{event.id}-{i + 1:04d}",
            gold={
                "category": sample.expected.category,
                "sender_type": sample.expected.sender_type,
                "fields": sample.expected.fields,
            },
            queued_at=now - timedelta(seconds=(volume - i) * 10),
        )
        email.event_id = event.id
    await session.commit()
    return event


async def end_event(session: AsyncSession, event_id: int, actor: str) -> CrisisEvent:
    event = await session.get(CrisisEvent, event_id)
    if event is None:
        raise NotFound("Événement introuvable")
    if event.ended_at is not None:
        raise Conflict("Événement déjà clôturé")
    event.ended_at = utcnow()
    await append_event(session, "crisis.ended", actor, {"event_id": event.id})
    await session.commit()
    return event


async def event_report(session: AsyncSession, event: CrisisEvent) -> dict[str, Any]:
    now = utcnow()
    champion = await get_champion(session)
    emails = list(
        (
            await session.execute(
                select(Email)
                .where(Email.event_id == event.id)
                .options(selectinload(Email.suggestions), selectinload(Email.reviews))
            )
        ).scalars()
    )
    open_cases = [e for e in emails if e.status == "nouveau"]
    closed = [e for e in emails if e.closed_at is not None]
    last_hour = [e for e in closed if e.closed_at and e.closed_at >= now - timedelta(hours=1)]
    per_hour = len(last_hour)
    by_arm: dict[str, float | None] = {}
    for arm in ("ai", "control"):
        times = [e.reviews[0].seconds_to_decision for e in closed if e.reviews and e.arm == arm]
        by_arm[arm] = round(statistics.median(times), 1) if times else None
    return {
        "id": event.id,
        "name": event.name,
        "kind": event.kind,
        "kind_label": KINDS.get(event.kind, event.kind),
        "started_at": event.started_at.isoformat(),
        "ended_at": event.ended_at.isoformat() if event.ended_at else None,
        "received": len(emails),
        "open": len(open_cases),
        "closed": len(closed),
        "late": sum(1 for e in open_cases if case_sla(e, now, champion).state == "en_retard"),
        "urgent_open": sum(
            1
            for e in open_cases
            for s in [next((x for x in reversed(e.suggestions)), None)]
            if s is not None and s.priority == "urgente"
        ),
        "waiting_analysis": sum(
            1 for e in open_cases if e.analysis_status in ("pending", "running")
        ),
        "closed_last_hour": per_hour,
        # At the pace of the last hour, how long until the event backlog is cleared?
        "hours_to_clear": round(len(open_cases) / per_hour, 1) if per_hour else None,
        "median_seconds": by_arm,
    }

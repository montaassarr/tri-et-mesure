"""Intake: an e-mail enters the system, is masked, and waits for analysis.

Intake never calls the model. It only records the e-mail and marks it `pending`; the
analysis worker picks it up. A slow or unavailable model therefore never blocks intake.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tri_mesure.audit.store import append_event
from tri_mesure.db.models import Email, utcnow
from tri_mesure.pipeline import mask_email
from tri_mesure.settings import REPO_ROOT

ACTOR = "system:intake"


def _hash_int(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest(), 16)


def assign_arm(key: str) -> str:
    """Deterministic 50/50 split: same e-mail, same arm, on every machine."""
    return "control" if _hash_int(key) % 2 else "ai"


async def ingest_email(
    session: AsyncSession,
    *,
    subject: str,
    body: str,
    sender_email: str,
    received_at: datetime,
    external_id: str | None = None,
    gold: dict[str, Any] | None = None,
    arm: str | None = None,
    queued_at: datetime | None = None,
) -> Email:
    masked = mask_email(subject, body)
    email = Email(
        external_id=external_id,
        received_at=received_at if received_at.tzinfo else received_at.replace(tzinfo=UTC),
        sender_email=sender_email,
        subject=subject,
        body_raw=body,
        subject_masked=masked.subject,
        body_masked=masked.body,
        pii_counts=masked.result.counts(),
        arm=arm or assign_arm(external_id or f"{sender_email}{received_at.isoformat()}"),
        status="nouveau",
        analysis_status="pending",
        analysis_attempts=0,
        queued_at=queued_at or utcnow(),
        gold=gold,
    )
    session.add(email)
    await session.flush()
    await append_event(
        session, "email.received", ACTOR, {"external_id": external_id, "arm": email.arm}, email.id
    )
    await append_event(session, "pii.masked", ACTOR, {"counts": email.pii_counts}, email.id)
    return email


async def seed_demo(session: AsyncSession, dataset: str = "demo") -> tuple[int, int]:
    """Load synthetic e-mails. Their queue arrival is spread over the last 6 hours so the
    service-level clocks look like a real morning (documented as simulated)."""
    path = REPO_ROOT / "data" / "gold" / f"{dataset}.jsonl"
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    existing = set(
        (
            await session.execute(select(Email.external_id).where(Email.external_id.is_not(None)))
        ).scalars()
    )
    now = utcnow()
    created = skipped = 0
    for sample in samples:
        if sample["id"] in existing:
            skipped += 1
            continue
        await ingest_email(
            session,
            subject=sample["subject"],
            body=sample["body"],
            sender_email=sample["sender_email"],
            received_at=datetime.fromisoformat(sample["received_at"]),
            external_id=sample["id"],
            gold=sample["expected"],
            queued_at=now - timedelta(minutes=_hash_int(sample["id"]) % 360),
        )
        created += 1
    await session.commit()
    return created, skipped

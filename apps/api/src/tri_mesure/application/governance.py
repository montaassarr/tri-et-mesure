"""Governance: retention purge and the processing register shown to the auditor."""

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tri_mesure.audit.store import append_event, verify_chain
from tri_mesure.db.models import AuditEvent, Email, LLMCall, Review, Suggestion, utcnow
from tri_mesure.domain.roles import ROLES, SYSTEM_ACTORS
from tri_mesure.pii.masker import PATTERNS
from tri_mesure.settings import Settings

RETENTION_ACTOR = "system:retention"


async def purge_raw_bodies(session: AsyncSession, retention_days: int) -> int:
    cutoff = utcnow() - timedelta(days=retention_days)
    result = await session.execute(
        update(Email)
        .where(Email.created_at < cutoff, Email.body_raw.is_not(None))
        .values(body_raw=None)
    )
    purged = int(getattr(result, "rowcount", 0) or 0)
    if purged:
        await append_event(
            session,
            "retention.purged",
            RETENTION_ACTOR,
            {"count": purged, "retention_days": retention_days},
        )
    await session.commit()
    return purged


async def processing_register(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    """A short, GDPR-style description of the processing, with live evidence."""
    emails = list((await session.execute(select(Email.pii_counts, Email.body_raw))).all())
    masked: dict[str, int] = {}
    for counts, _ in emails:
        for kind, n in (counts or {}).items():
            masked[kind] = masked.get(kind, 0) + int(n)
    providers = sorted(
        set((await session.execute(select(LLMCall.gen_ai_system).distinct())).scalars())
    )
    events = int((await session.execute(select(func.count()).select_from(AuditEvent))).scalar_one())
    chain = await verify_chain(session)
    return {
        "purpose": "Tri du courrier sinistres assisté par IA, avec décision humaine (prototype).",
        "data_categories": [
            "Identité et coordonnées de l'expéditeur",
            "Numéros de contrat et d'immatriculation",
            "Description du sinistre (peut contenir des données sensibles)",
        ],
        "minimisation": {
            "masked_before_model": [*sorted(PATTERNS), "PERSONNE (signature)"],
            "not_masked": ["Adresses postales (limite connue)"],
            "masked_entities_total": masked,
        },
        "retention": {
            "raw_text_days": settings.raw_retention_days,
            "raw_text_still_stored": sum(1 for _, body in emails if body is not None),
            "raw_text_purged": sum(1 for _, body in emails if body is None),
            "kept": "Version masquée, décisions et journal d'audit",
        },
        "recipients": {
            "model_providers_used": providers,
            "what_they_receive": "Texte masqué uniquement ; aucune donnée d'identification.",
        },
        "access": {code: sorted(r.permissions) for code, r in ROLES.items()},
        "system_actors": SYSTEM_ACTORS,
        "audit": {"events": events, "chain_ok": chain.ok},
        "decisions_by_ai": "Aucune : l'IA propose, un humain authentifié décide.",
    }


async def oversight_report(
    session: AsyncSession, settings: Settings, days: int, actor: str
) -> dict[str, Any]:
    """Human-oversight report for a period: who decided, with which AI, what went wrong.

    Generating the report is itself audited, and the report carries the current head of the
    audit chain as a seal: anyone can later check the log has not changed since.
    """
    end = utcnow()
    start = end - timedelta(days=days)
    reviews = list(
        (await session.execute(select(Review).where(Review.created_at >= start))).scalars()
    )
    suggestions = {
        s.id: s
        for s in (
            await session.execute(select(Suggestion).where(Suggestion.created_at >= start))
        ).scalars()
    }
    events = list(
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.ts >= start.isoformat(timespec="milliseconds"))
            )
        ).scalars()
    )
    by_type = Counter(e.type for e in events)
    ai_reviews = [r for r in reviews if r.arm == "ai"]
    as_is = sum(1 for r in ai_reviews if all(v == "accepted" for v in r.verdicts.values()))
    corrections: Counter[str] = Counter()
    for r in ai_reviews:
        for item, verdict in r.verdicts.items():
            if verdict in ("edited", "rejected"):
                corrections[item] += 1
    systems = Counter(f"{s.source} · {s.model} · {s.prompt_version}" for s in suggestions.values())
    shown = Counter(
        f"{suggestions[r.suggestion_id].source} · {suggestions[r.suggestion_id].model}"
        for r in ai_reviews
        if r.suggestion_id in suggestions
    )
    changes = [
        {"ts": e.ts, "type": e.type, "actor": e.actor, "payload": e.payload}
        for e in events
        if e.type
        in (
            "config.changed",
            "champion.changed",
            "source.created",
            "source.updated",
            "assumption.updated",
            "crisis.started",
            "crisis.ended",
        )
    ]
    chain = await verify_chain(session)
    head = (
        await session.execute(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    ).scalar_one_or_none()
    report = {
        "period": {"from": start.isoformat(), "to": end.isoformat(), "days": days},
        "generated_by": actor,
        "decisions": {
            "total": len(reviews),
            "by_authenticated_human": sum(1 for r in reviews if r.reviewer and r.reviewer_role),
            "with_ai_proposal": len(ai_reviews),
            "without_ai_control_arm": len(reviews) - len(ai_reviews),
            "manual_handling": sum(1 for r in reviews if r.manual),
            "ai_accepted_as_is": as_is,
            "corrections_by_item": dict(corrections.most_common()),
            "rejection_reasons": dict(Counter(r.reason_code for r in reviews if r.reason_code)),
            "reviewers": len({r.reviewer for r in reviews}),
        },
        "ai_systems": {
            "suggestions_by_system": dict(systems.most_common()),
            "shown_to_handlers_by_system": dict(shown.most_common()),
            "fallbacks_to_rules": sum(1 for s in suggestions.values() if s.used_fallback),
            "analysis_failures": by_type.get("ai.failed", 0),
        },
        "changes": changes,
        "privacy": {
            "emails_masked": by_type.get("pii.masked", 0),
            "raw_text_purges": by_type.get("retention.purged", 0),
            "what_vendors_receive": "Texte masqué uniquement",
        },
        "integrity": {
            "chain_ok": chain.ok,
            "events_checked": chain.checked,
            "events_in_period": len(events),
            "seal_seq": head.seq if head else None,
            "seal_hash": head.hash if head else None,
        },
        "statement": (
            "Aucune décision n'a été prise par l'IA : chaque dossier clos l'a été par une "
            "personne authentifiée, identifiée dans le journal."
        ),
    }
    await append_event(
        session,
        "report.generated",
        actor,
        {"days": days, "seal_seq": head.seq if head else None},
    )
    await session.commit()
    return report

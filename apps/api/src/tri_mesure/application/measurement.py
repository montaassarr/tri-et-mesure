"""Measurement: what the manager and the AI team look at.

Two audiences, two views, one data source:
- `pilotage()` — the team lead: stock, deadlines, throughput, measured value of the AI.
  Team-level aggregates only: no per-person ranking or timing (a deliberate choice, see
  docs/actors-and-roles.md).
- `production_quality()` — the AI team: how humans judged each suggestion in production.

Measured values are always kept apart from assumptions, which are editable and labelled.
"""

import statistics
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tri_mesure.application.casework import case_sla, visible_suggestion
from tri_mesure.application.errors import NotFound
from tri_mesure.application.sources import get_champion
from tri_mesure.audit.store import append_event
from tri_mesure.db.models import (
    DEFAULT_ASSUMPTIONS,
    Assumption,
    Email,
    LLMCall,
    Review,
    Suggestion,
    utcnow,
)
from tri_mesure.domain.casework import SLA_HOURS
from tri_mesure.domain.taxonomy import PRIORITY_ORDER

MIN_PER_ARM = 5


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def _pct(values: list[int], q: int) -> int | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return int(statistics.quantiles(values, n=100, method="inclusive")[q - 1])


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


async def ensure_assumptions(session: AsyncSession) -> None:
    existing = set((await session.execute(select(Assumption.key))).scalars())
    for a in DEFAULT_ASSUMPTIONS:
        if a["key"] not in existing:
            session.add(Assumption(**a))
    await session.commit()


async def list_assumptions(session: AsyncSession) -> list[Assumption]:
    return list((await session.execute(select(Assumption).order_by(Assumption.key))).scalars())


async def update_assumption(
    session: AsyncSession, key: str, value: float, actor: str
) -> Assumption:
    a = await session.get(Assumption, key)
    if a is None:
        raise NotFound("Hypothèse inconnue")
    old = a.value
    a.value, a.updated_at = value, utcnow()
    await append_event(session, "assumption.updated", actor, {"key": key, "from": old, "to": value})
    await session.commit()
    return a


def _arm_stats(reviews: list[Review], gold: dict[int, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for arm in ("ai", "control"):
        rs = [r for r in reviews if r.arm == arm]
        graded = [r for r in rs if r.email_id in gold]
        correct = sum(1 for r in graded if r.category == gold[r.email_id]["category"])
        out[arm] = {
            "n": len(rs),
            "median_seconds": _median([r.seconds_to_decision for r in rs]),
            "category_accuracy": _rate(correct, len(graded)),
        }
    return out


async def pilotage(session: AsyncSession, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    emails = list(
        (await session.execute(select(Email).options(selectinload(Email.suggestions)))).scalars()
    )
    reviews = list((await session.execute(select(Review))).scalars())
    calls = list((await session.execute(select(LLMCall))).scalars())
    assumptions = {a.key: a.value for a in await list_assumptions(session)}
    gold = {e.id: e.gold for e in emails if e.gold}

    champion = await get_champion(session)
    open_cases = [e for e in emails if e.status == "nouveau"]
    backlog = {p: 0 for p in PRIORITY_ORDER} | {"non_triee": 0}
    late = Counter[str]()
    due_soon = 0
    for e in open_cases:
        s = visible_suggestion(e, champion)
        key = s.priority if s else "non_triee"
        backlog[key] += 1
        sla = case_sla(e, now, champion)
        if sla.state == "en_retard":
            late[key] += 1
        elif sla.state == "bientot":
            due_soon += 1

    closed = [e for e in emails if e.closed_at is not None]
    closed_today = [e for e in closed if e.closed_at and e.closed_at.date() == now.date()]
    within = 0
    for e in closed:
        s = e.suggestions[-1] if e.suggestions and e.arm == "ai" else None
        hours = SLA_HOURS.get(s.priority if s else "normale", 72)
        if e.closed_at and e.closed_at <= e.queued_at + timedelta(hours=hours):
            within += 1

    arms = _arm_stats(reviews, gold)
    enough = arms["ai"]["n"] >= MIN_PER_ARM and arms["control"]["n"] >= MIN_PER_ARM
    saved: float | None = None
    if (
        enough
        and arms["ai"]["median_seconds"] is not None
        and arms["control"]["median_seconds"] is not None
    ):
        saved = round(arms["control"]["median_seconds"] - arms["ai"]["median_seconds"], 1)
    volume = assumptions.get("monthly_volume", 0.0)
    hourly = assumptions.get("cost_per_hour", 0.0)
    ai_reviews = [r for r in reviews if r.arm == "ai"]
    as_is = sum(1 for r in ai_reviews if all(v == "accepted" for v in r.verdicts.values()))
    suggestion_count = sum(len(e.suggestions) for e in emails)
    cost_total = sum(c.cost_eur or 0.0 for c in calls if c.purpose == "suggest")
    cost_per_email = cost_total / suggestion_count if suggestion_count else 0.0

    return {
        "generated_at": now.isoformat(),
        "stock": {
            "open": len(open_cases),
            "by_priority": backlog,
            "late": sum(late.values()),
            "late_by_priority": dict(late),
            "due_soon": due_soon,
            "waiting_analysis": sum(
                1 for e in open_cases if e.analysis_status in ("pending", "running")
            ),
            "analysis_failed": sum(1 for e in emails if e.analysis_status == "failed"),
        },
        "flow": {
            "closed_total": len(closed),
            "closed_today": len(closed_today),
            "within_target_rate": _rate(within, len(closed)),
            "manual_rate": _rate(sum(1 for e in closed if e.status == "manuel"), len(closed)),
        },
        "ai_value": {
            "arms": arms,
            "enough_data": enough,
            "min_per_arm": MIN_PER_ARM,
            "seconds_saved_per_case": saved,
            "accepted_as_is_rate": _rate(as_is, len(ai_reviews)),
            "cost_eur_per_email": round(cost_per_email, 6),
        },
        "estimate": {
            "monthly_hours_saved": round(saved * volume / 3600, 1) if saved is not None else None,
            "monthly_value_eur": round(saved * volume / 3600 * hourly)
            if saved is not None
            else None,
            "monthly_model_cost_eur": round(cost_per_email * volume, 2),
            "formula": "(médiane sans IA − médiane avec IA) × volume mensuel ÷ 3600 × coût horaire",
            "warning": "Données synthétiques et petit pilote : à ne pas extrapoler.",
        },
        "sla_targets_hours": SLA_HOURS,
        "privacy_note": "Indicateurs d'équipe uniquement : aucun suivi individuel.",
    }


async def production_quality(session: AsyncSession) -> dict[str, Any]:
    """How handlers judged AI suggestions in production (AI arm only)."""
    reviews = list((await session.execute(select(Review).where(Review.arm == "ai"))).scalars())
    suggestions = {s.id: s for s in (await session.execute(select(Suggestion))).scalars()}
    calls = list((await session.execute(select(LLMCall))).scalars())

    per_item: dict[str, dict[str, int]] = {}
    for r in reviews:
        for item, verdict in r.verdicts.items():
            counts = per_item.setdefault(item, {"accepted": 0, "edited": 0, "rejected": 0})
            if verdict in counts:
                counts[verdict] += 1

    by_version: dict[str, dict[str, Any]] = {}
    for r in reviews:
        s = suggestions.get(r.suggestion_id) if r.suggestion_id else None
        key = f"{s.source} · {s.model} · {s.prompt_version}" if s else "inconnu"
        v = by_version.setdefault(key, {"n": 0, "category_accepted": 0})
        v["n"] += 1
        v["category_accepted"] += r.verdicts.get("category") == "accepted"
    for v in by_version.values():
        v["category_acceptance_rate"] = _rate(v["category_accepted"], v["n"])

    model_calls = [c for c in calls if c.gen_ai_system != "rules"]
    latencies = [c.latency_ms for c in model_calls]
    return {
        "reviews": len(reviews),
        "per_item": per_item,
        "by_model_and_prompt": by_version,
        "rejection_reasons": dict(Counter(r.reason_code for r in reviews if r.reason_code)),
        "calls": {
            "total": len(calls),
            "model_calls": len(model_calls),
            "schema_valid_rate": _rate(sum(c.schema_valid for c in model_calls), len(model_calls)),
            "fallback_rate": _rate(
                sum(1 for s in suggestions.values() if s.used_fallback), len(suggestions)
            ),
            "cost_eur_total": round(sum(c.cost_eur or 0.0 for c in calls), 6),
            "latency_p50_ms": _pct(latencies, 50),
            "latency_p95_ms": _pct(latencies, 95),
            "cache_read_tokens": sum(c.cache_read_tokens for c in calls),
        },
    }

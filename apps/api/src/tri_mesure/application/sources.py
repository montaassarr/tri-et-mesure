"""Vendor-neutral control tower for AI suggestions.

Any AI system can plug in: our own pipeline ("interne") or an external vendor that calls
the ingestion API with its own key. Exactly one source is the **champion**: its
suggestions are shown to handlers. The others run in **shadow mode**: they propose on the
same cases, nobody sees their output, and they are scored once the human has decided.

Scoring has a known bias: handlers tend to agree with what they were shown, which favours
the champion. The **unbiased** score therefore uses control-arm cases only, where the
human decided without seeing any AI. Synthetic data also carries ground truth.
"""

import hashlib
import re
import secrets
import statistics
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tri_mesure.application.errors import Conflict, Invalid, NotFound
from tri_mesure.audit.store import append_event
from tri_mesure.db.models import AISource, AppConfig, Email, Review, Suggestion, utcnow
from tri_mesure.domain.priority_rules import compute_priority
from tri_mesure.domain.schemas import ExtractedFields, Extraction
from tri_mesure.domain.taxonomy import MANUAL_REVIEW_CONFIDENCE
from tri_mesure.evaluation.metrics import field_match
from tri_mesure.pipeline import evidence_spans, mask_email, unmask_fields

INTERNAL = "interne"
CHAMPION_KEY = "champion_source"
KEY_PREFIX = "tm_"


def hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def _slug(name: str) -> str:
    text = unicodedata.normalize("NFD", name.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:30] or "source"


# --- registry ----------------------------------------------------------------------


async def ensure_internal_source(session: AsyncSession) -> None:
    if await session.get(AISource, INTERNAL) is None:
        session.add(AISource(code=INTERNAL, name="Pipeline interne", kind="internal"))
        await session.commit()


async def list_sources(session: AsyncSession) -> list[AISource]:
    return list((await session.execute(select(AISource).order_by(AISource.created_at))).scalars())


async def create_source(session: AsyncSession, name: str, actor: str) -> tuple[AISource, str]:
    """Register an external vendor. The API key is returned once and never stored."""
    base = _slug(name)
    code, n = base, 2
    while await session.get(AISource, code) is not None:
        code, n = f"{base}-{n}", n + 1
    api_key = KEY_PREFIX + secrets.token_urlsafe(32)
    source = AISource(
        code=code,
        name=name.strip(),
        kind="external",
        api_key_hash=hash_key(api_key),
        created_by=actor,
    )
    session.add(source)
    await append_event(session, "source.created", actor, {"source": code, "name": source.name})
    await session.commit()
    return source, api_key


async def set_active(session: AsyncSession, code: str, active: bool, actor: str) -> AISource:
    source = await session.get(AISource, code)
    if source is None:
        raise NotFound("Source inconnue")
    if not active and code == await get_champion(session):
        raise Conflict(
            "Impossible de désactiver la source championne : changez d'abord de champion"
        )
    source.active = active
    await append_event(session, "source.updated", actor, {"source": code, "active": active})
    await session.commit()
    return source


async def authenticate(session: AsyncSession, api_key: str) -> AISource | None:
    if not api_key.startswith(KEY_PREFIX):
        return None
    source = (
        await session.execute(select(AISource).where(AISource.api_key_hash == hash_key(api_key)))
    ).scalar_one_or_none()
    return source if source is not None and source.active and source.kind == "external" else None


async def get_champion(session: AsyncSession) -> str:
    row = await session.get(AppConfig, CHAMPION_KEY)
    return row.value if row else INTERNAL


async def set_champion(session: AsyncSession, code: str, actor: str) -> str:
    source = await session.get(AISource, code)
    if source is None or not source.active:
        raise Invalid("Source inconnue ou inactive")
    before = await get_champion(session)
    row = await session.get(AppConfig, CHAMPION_KEY)
    if row is None:
        session.add(AppConfig(key=CHAMPION_KEY, value=code, updated_by=actor))
    else:
        row.value, row.updated_by, row.updated_at = code, actor, utcnow()
    await append_event(session, "champion.changed", actor, {"from": before, "to": code})
    await session.commit()
    return code


# --- which suggestion a handler sees -------------------------------------------------


def displayed_suggestion(email: Email, champion: str) -> Suggestion | None:
    """The champion's latest suggestion; the internal one if the champion has none yet."""
    own = [s for s in email.suggestions if s.source == champion]
    if own:
        return own[-1]
    internal = [s for s in email.suggestions if s.source == INTERNAL]
    return internal[-1] if internal else None


# --- ingestion from external vendors --------------------------------------------------


async def pending_for(session: AsyncSession, source: AISource, limit: int) -> list[Email]:
    """Open cases this vendor has not proposed on yet (it only ever sees masked text)."""
    done = select(Suggestion.email_id).where(Suggestion.source == source.code)
    rows = await session.execute(
        select(Email)
        .where(Email.status == "nouveau", Email.id.not_in(done))
        .order_by(Email.queued_at)
        .limit(limit)
    )
    return list(rows.scalars())


async def submit_external(
    session: AsyncSession,
    source: AISource,
    email_id: int,
    extraction: Extraction,
    model: str,
    cost_eur: float | None,
    latency_ms: int | None,
) -> Suggestion:
    email = (
        await session.execute(
            select(Email).where(Email.id == email_id).options(selectinload(Email.suggestions))
        )
    ).scalar_one_or_none()
    if email is None:
        raise NotFound("Dossier introuvable")
    if email.status != "nouveau":
        raise Conflict("Dossier déjà clôturé : les propositions tardives ne sont pas acceptées")
    if any(s.source == source.code for s in email.suggestions):
        raise Conflict("Cette source a déjà proposé sur ce dossier")

    extraction = extraction.normalise()
    # Vendors work on masked text; map their placeholders back to real values server-side.
    mapping = mask_email(email.subject, email.body_raw).result.mapping if email.body_raw else {}
    fields = unmask_fields(extraction, mapping)
    spans = evidence_spans(extraction, mapping, email.body_raw) if email.body_raw else []
    priority = compute_priority(
        extraction.category, ExtractedFields(**fields), email.received_at.date()
    )
    low = extraction.confidence < MANUAL_REVIEW_CONFIDENCE
    suggestion = Suggestion(
        email_id=email.id,
        source=source.code,
        provider="external",
        model=model[:80],
        prompt_version="externe",
        latency_ms=latency_ms,
        category=extraction.category,
        sender_type=extraction.sender_type,
        confidence=extraction.confidence,
        fields=fields,
        spans=spans,
        summary=extraction.summary,
        priority=priority.priority,
        priority_reasons=priority.reasons,
        needs_manual=low,
        manual_reason=f"Confiance faible ({extraction.confidence:.2f})" if low else None,
        used_fallback=False,
        cost_eur=cost_eur or 0.0,
    )
    session.add(suggestion)
    await session.flush()
    mode = "champion" if source.code == await get_champion(session) else "shadow"
    await append_event(
        session,
        "ai.suggested",
        f"ai:{source.code}",
        {
            "suggestion_id": suggestion.id,
            "source": source.code,
            "model": model,
            "mode": mode,
            "category": extraction.category,
            "confidence": extraction.confidence,
            "cost_eur": cost_eur,
        },
        email.id,
    )
    await session.commit()
    return suggestion


# --- the scoreboard ------------------------------------------------------------------


def _rate(part: float, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _field_agreement(s: Suggestion, r: Review) -> tuple[int, int]:
    names = set(r.fields) | {k for k, v in s.fields.items() if v is not None}
    matched = sum(1 for n in names if field_match(n, r.fields.get(n), s.fields.get(n)))
    return matched, len(names)


async def scoreboard(session: AsyncSession) -> list[dict[str, Any]]:
    sources = await list_sources(session)
    champion = await get_champion(session)
    emails = list(
        (
            await session.execute(
                select(Email).options(selectinload(Email.suggestions), selectinload(Email.reviews))
            )
        ).scalars()
    )
    total_cases = len(emails)
    out: list[dict[str, Any]] = []
    for src in sources:
        suggestions = 0
        scored = agree = unbiased_n = unbiased_agree = gold_n = gold_ok = shown = 0
        f_match = f_total = 0
        costs: list[float] = []
        latencies: list[int] = []
        for e in emails:
            mine = [s for s in e.suggestions if s.source == src.code]
            if not mine:
                continue
            s = mine[-1]
            suggestions += 1
            costs.append(s.cost_eur or 0.0)
            if s.latency_ms is not None:
                latencies.append(s.latency_ms)
            if e.gold:
                gold_n += 1
                gold_ok += s.category == e.gold.get("category")
            if not e.reviews:
                continue
            r = e.reviews[0]
            scored += 1
            agree += s.category == r.category
            m, t = _field_agreement(s, r)
            f_match, f_total = f_match + m, f_total + t
            shown += r.suggestion_id == s.id
            if r.arm == "control":
                unbiased_n += 1
                unbiased_agree += s.category == r.category
        out.append(
            {
                "code": src.code,
                "name": src.name,
                "kind": src.kind,
                "active": src.active,
                "champion": src.code == champion,
                "suggestions": suggestions,
                "coverage": _rate(suggestions, total_cases),
                "scored_cases": scored,
                "shown_to_handlers": shown,
                "category_agreement": _rate(agree, scored),
                "category_agreement_unbiased": _rate(unbiased_agree, unbiased_n),
                "unbiased_cases": unbiased_n,
                "field_agreement": _rate(f_match, f_total),
                "ground_truth_accuracy": _rate(gold_ok, gold_n),
                "cost_eur_per_suggestion": round(statistics.fmean(costs), 6) if costs else None,
                "latency_p50_ms": int(statistics.median(latencies)) if latencies else None,
            }
        )
    return out

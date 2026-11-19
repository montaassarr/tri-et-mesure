"""Casework: the handler's journey — queue, take a case, decide, close.

Rules that matter for trust:
- the control arm never shows AI output before the case is closed (unbiased baseline);
- a case is taken by one handler at a time (lease), so two people never decide twice;
- the database enforces one closing decision per case, even under a race;
- every step is written to the audit log under the authenticated person's name.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tri_mesure.application.errors import Conflict, NotFound
from tri_mesure.application.sources import INTERNAL, displayed_suggestion, get_champion
from tri_mesure.audit.store import append_event
from tri_mesure.db.models import AuditEvent, Email, LLMCall, Review, Suggestion, utcnow
from tri_mesure.domain.casework import Sla, can_claim, claim_holder, sla_for
from tri_mesure.domain.taxonomy import PRIORITY_ORDER
from tri_mesure.observability import CASES_CLOSED, DECISIONS

REASON_CODES: dict[str, str] = {
    "mauvaise_categorie": "Catégorie incorrecte",
    "valeur_inventee": "Valeur absente de l'e-mail (inventée)",
    "valeur_incomplete": "Valeur incomplète ou mal lue",
    "hors_perimetre": "Hors périmètre de l'outil",
    "autre": "Autre motif",
}


@dataclass(frozen=True)
class Actor:
    """Who performs an action (built by the API from the authenticated token)."""

    name: str
    role: str

    @property
    def audit_name(self) -> str:
        return f"human:{self.name} ({self.role})"


@dataclass
class FieldDecision:
    verdict: str  # accepted | edited | rejected | manual_entry
    value: Any = None


@dataclass
class ReviewCommand:
    category: FieldDecision
    fields: dict[str, FieldDecision] = field(default_factory=dict)
    reason_code: str | None = None
    manual: bool = False
    seconds_to_decision: float = 0.0


@dataclass
class CaseView:
    email: Email
    suggestion: Suggestion | None  # None when hidden (control arm) or not analysed yet
    sla: Sla
    holder: str | None
    calls: list[LLMCall] = field(default_factory=list)


def visible_suggestion(email: Email, champion: str = INTERNAL) -> Suggestion | None:
    """What a handler may see: nothing on an open control-arm case, else the champion's."""
    if email.arm == "control" and email.status == "nouveau":
        return None
    return displayed_suggestion(email, champion)


def case_sla(email: Email, now: datetime, champion: str = INTERNAL) -> Sla:
    # Control arm: no AI triage, so the standard target applies (see domain/casework.py).
    s = visible_suggestion(email, champion)
    return sla_for(s.priority if s else None, email.queued_at, now, email.status != "nouveau")


async def load_email(session: AsyncSession, email_id: int) -> Email:
    email = (
        await session.execute(
            select(Email)
            .where(Email.id == email_id)
            .options(selectinload(Email.suggestions), selectinload(Email.reviews))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if email is None:
        raise NotFound("Dossier introuvable")
    return email


async def list_queue(session: AsyncSession, now: datetime | None = None) -> list[CaseView]:
    now = now or utcnow()
    champion = await get_champion(session)
    emails = (
        (await session.execute(select(Email).options(selectinload(Email.suggestions))))
        .scalars()
        .all()
    )
    views = [
        CaseView(
            e,
            visible_suggestion(e, champion),
            case_sla(e, now, champion),
            claim_holder(e.assigned_to, e.assigned_at, now),
        )
        for e in emails
    ]
    # Open first; then urgent first; then the case closest to (or furthest past) its target.
    views.sort(
        key=lambda v: (
            v.email.status != "nouveau",
            PRIORITY_ORDER.get(v.suggestion.priority if v.suggestion else "normale", 2),
            v.sla.due_at,
        )
    )
    return views


async def get_case(session: AsyncSession, email_id: int, now: datetime | None = None) -> CaseView:
    now = now or utcnow()
    champion = await get_champion(session)
    email = await load_email(session, email_id)
    suggestion = visible_suggestion(email, champion)
    calls: list[LLMCall] = []
    if suggestion is not None and suggestion.source == INTERNAL:  # vendors have no ledger here
        calls = list(
            (
                await session.execute(
                    select(LLMCall).where(LLMCall.email_id == email.id).order_by(LLMCall.id)
                )
            ).scalars()
        )
    return CaseView(
        email,
        suggestion,
        case_sla(email, now, champion),
        claim_holder(email.assigned_to, email.assigned_at, now),
        calls,
    )


async def claim_case(session: AsyncSession, email_id: int, actor: Actor) -> CaseView:
    now = utcnow()
    email = await load_email(session, email_id)
    decision = can_claim(email.status, email.assigned_to, email.assigned_at, actor.name, now)
    if not decision.allowed:
        raise Conflict(decision.reason or "Dossier indisponible")
    already_mine = claim_holder(email.assigned_to, email.assigned_at, now) == actor.name
    email.assigned_to, email.assigned_at = actor.name, now
    if not already_mine:
        await append_event(session, "case.claimed", actor.audit_name, {}, email.id)
    await session.commit()
    return await get_case(session, email_id, now)


async def release_case(session: AsyncSession, email_id: int, actor: Actor) -> None:
    now = utcnow()
    email = await load_email(session, email_id)
    if claim_holder(email.assigned_to, email.assigned_at, now) != actor.name:
        raise Conflict("Ce dossier n'est pas pris en charge par vous")
    email.assigned_to, email.assigned_at = None, None
    await append_event(session, "case.released", actor.audit_name, {}, email.id)
    await session.commit()


async def submit_review(
    session: AsyncSession, email_id: int, command: ReviewCommand, actor: Actor
) -> Review:
    now = utcnow()
    email = await load_email(session, email_id)
    decision = can_claim(email.status, email.assigned_to, email.assigned_at, actor.name, now)
    if not decision.allowed:
        raise Conflict(decision.reason or "Dossier indisponible")
    if email.arm == "ai" and email.analysis_status in ("pending", "running"):
        raise Conflict("Analyse IA en cours : réessayez dans quelques secondes")

    # The decision is attributed to the suggestion the handler actually saw (the champion's).
    suggestion = displayed_suggestion(email, await get_champion(session))
    suggested_fields = suggestion.fields if suggestion else {}
    final_fields = {name: d.value for name, d in command.fields.items()}
    verdicts = {"category": command.category.verdict} | {
        name: d.verdict for name, d in command.fields.items()
    }
    diff: dict[str, Any] = {}
    if suggestion and command.category.value != suggestion.category:
        diff["category"] = {"from": suggestion.category, "to": command.category.value}
    for name, value in final_fields.items():
        before = suggested_fields.get(name)
        if value != before:
            diff[name] = {"from": before, "to": value}

    review = Review(
        email_id=email.id,
        suggestion_id=suggestion.id if suggestion else None,
        reviewer=actor.name,
        reviewer_role=actor.role,
        arm=email.arm,
        category=str(command.category.value),
        fields=final_fields,
        verdicts=verdicts,
        diff=diff,
        reason_code=command.reason_code,
        manual=command.manual,
        seconds_to_decision=command.seconds_to_decision,
    )
    session.add(review)
    await session.flush()  # the unique constraint fires here if another decision won a race

    for item, verdict in verdicts.items():
        DECISIONS.labels(verdict).inc()
        if verdict == "accepted":
            await append_event(
                session, "human.accepted", actor.audit_name, {"item": item}, email.id
            )
        elif verdict == "edited":
            await append_event(
                session,
                "human.edited",
                actor.audit_name,
                {"item": item, "diff": diff.get(item)},
                email.id,
            )
        elif verdict == "rejected":
            await append_event(
                session,
                "human.rejected",
                actor.audit_name,
                {"item": item, "reason_code": command.reason_code},
                email.id,
            )

    email.status = "manuel" if command.manual else "traite"
    email.closed_at = now
    email.assigned_to, email.assigned_at = None, None
    sla = sla_for(
        suggestion.priority if suggestion and email.arm == "ai" else None,
        email.queued_at,
        now,
        closed=False,
    )
    await append_event(
        session,
        "case.closed",
        actor.audit_name,
        {
            "review_id": review.id,
            "status": email.status,
            "arm": email.arm,
            "seconds_to_decision": command.seconds_to_decision,
            "within_target": sla.minutes_left >= 0,
        },
        email.id,
    )
    await session.commit()
    CASES_CLOSED.labels(email.arm, email.status).inc()
    return review


async def next_case_id(session: AsyncSession, actor: Actor) -> int | None:
    """The single "what should I do next?" answer: most urgent open case nobody holds."""
    now = utcnow()
    for view in await list_queue(session, now):
        if view.email.status != "nouveau":
            break
        if view.email.arm == "ai" and view.email.analysis_status in ("pending", "running"):
            continue
        if view.holder in (None, actor.name):
            return view.email.id
    return None


async def list_decisions(session: AsyncSession) -> list[Review]:
    return list((await session.execute(select(Review).order_by(Review.id))).scalars())


# --- case context: related cases and timeline -------------------------------------------

AI_EVENT_TYPES = ("ai.suggested", "priority.computed", "ai.failed", "ai.reanalysis_requested")


async def related_cases(
    session: AsyncSession, email_id: int, contract: str | None, limit: int = 8
) -> list[CaseView]:
    """Other cases from the same sender or about the same contract (relance, doublon…)."""
    email = await load_email(session, email_id)
    champion = await get_champion(session)
    now = utcnow()
    rows = (
        (
            await session.execute(
                select(Email)
                .where(Email.id != email_id)
                .options(selectinload(Email.suggestions))
                .order_by(Email.queued_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: list[CaseView] = []
    for e in rows:
        same_sender = e.sender_email == email.sender_email
        same_contract = (
            contract is not None
            and contract != ""
            and (contract in (e.body_raw or "") or contract in e.subject)
        )
        if same_sender or same_contract:
            out.append(
                CaseView(
                    e,
                    visible_suggestion(e, champion),
                    case_sla(e, now, champion),
                    claim_holder(e.assigned_to, e.assigned_at, now),
                )
            )
        if len(out) >= limit:
            break
    return out


async def case_timeline(session: AsyncSession, email_id: int) -> list[AuditEvent]:
    """The case's own audit events, oldest first. On an open control-arm case the AI's
    events are withheld, otherwise the timeline would reveal what the AI proposed."""
    email = await load_email(session, email_id)
    rows = list(
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.email_id == email_id).order_by(AuditEvent.seq)
            )
        ).scalars()
    )
    if email.arm == "control" and email.status == "nouveau":
        rows = [r for r in rows if r.type not in AI_EVENT_TYPES]
    return rows

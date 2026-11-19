"""Context for the handler's case screen: next steps, contract, related cases, history.

Playbook and contract are computed from what the handler has on screen (their current
values), not from hidden AI output, so the control arm stays unbiased.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from tri_mesure.api.deps import CanReadCases, SessionDep
from tri_mesure.api.schemas import (
    FrameOut,
    GuaranteeOut,
    PlaybookOut,
    PlaybookStepOut,
    PolicyOut,
    RelatedCase,
    TimelineEvent,
)
from tri_mesure.application import casework
from tri_mesure.domain import playbook, policies
from tri_mesure.domain.schemas import ExtractedFields
from tri_mesure.domain.taxonomy import CATEGORIES, DamageType

router = APIRouter(tags=["workspace"])


@router.get(
    "/playbook", response_model=PlaybookOut, summary="Next steps, legal frame, reply template"
)
async def get_playbook(
    _: CanReadCases,
    category: Annotated[str, Query(max_length=40)],
    numero_contrat: str | None = None,
    type_dommage: DamageType | None = None,
    besoin_relogement: bool | None = None,
    fuite_active: bool | None = None,
    personne_vulnerable: bool | None = None,
) -> PlaybookOut:
    cat = category if category in CATEGORIES else "autre"
    pb = playbook.build(
        cat,
        ExtractedFields(
            numero_contrat=numero_contrat,
            type_dommage=type_dommage,
            besoin_relogement=besoin_relogement,
            fuite_active=fuite_active,
            personne_vulnerable=personne_vulnerable,
        ),
    )
    return PlaybookOut(
        steps=[
            PlaybookStepOut(label=s.label, why=s.why, deadline=s.deadline, urgent=s.urgent)
            for s in pb.steps
        ],
        frames=[FrameOut(name=f.name, summary=f.summary, deadlines=f.deadlines) for f in pb.frames],
        reply_subject=pb.reply_subject,
        reply_body=pb.reply_body,
    )


@router.get(
    "/policies/{number}",
    response_model=PolicyOut | None,
    summary="Contract and coverage (simulated register)",
)
async def get_policy(
    number: str, _: CanReadCases, vehicle: bool = False, damage: DamageType | None = None
) -> PolicyOut | None:
    p = policies.lookup(number.strip()[:40], vehicle)
    if p is None:
        return None
    return PolicyOut(
        number=p.number,
        product=p.product,
        formula=p.formula,
        status=p.status,
        since=p.since.isoformat(),
        deductible_eur=p.deductible_eur,
        guarantees=[
            GuaranteeOut(code=g, label=policies.GUARANTEE_LABELS.get(g, g), included=inc)
            for g, inc in p.guarantees.items()
        ],
        covers_damage=p.covers(damage),
        simulated=p.simulated,
    )


@router.get(
    "/cases/{case_id}/related",
    response_model=list[RelatedCase],
    summary="Other cases from the same sender or about the same contract",
)
async def related(
    case_id: int, session: SessionDep, _: CanReadCases, contract: str | None = None
) -> list[RelatedCase]:
    email = await casework.load_email(session, case_id)
    return [
        RelatedCase(
            id=v.email.id,
            subject=v.email.subject,
            status=v.email.status,
            queued_at=v.email.queued_at,
            category=v.suggestion.category if v.suggestion else None,
            same_sender=v.email.sender_email == email.sender_email,
        )
        for v in await casework.related_cases(session, case_id, contract)
    ]


@router.get(
    "/cases/{case_id}/timeline",
    response_model=list[TimelineEvent],
    summary="What happened on this case, oldest first",
)
async def timeline(case_id: int, session: SessionDep, _: CanReadCases) -> list[TimelineEvent]:
    return [
        TimelineEvent(seq=e.seq, ts=e.ts, actor=e.actor, type=e.type, payload=e.payload)
        for e in await casework.case_timeline(session, case_id)
    ]

"""The handler's journey: queue, next case, take, decide."""

from typing import Annotated

from fastapi import APIRouter, Query

from tri_mesure.api.deps import CanReadCases, CanReview, CanSeed, SessionDep, actor_of
from tri_mesure.api.schemas import (
    CaseDetail,
    LLMCallOut,
    NextCaseOut,
    QueueItem,
    ReviewIn,
    ReviewOut,
    SeedOut,
    SlaOut,
    SuggestionOut,
)
from tri_mesure.application import casework, intake
from tri_mesure.application.casework import CaseView, FieldDecision, ReviewCommand
from tri_mesure.db.models import LLMCall
from tri_mesure.domain.casework import Sla
from tri_mesure.domain.taxonomy import MANUAL_REVIEW_CONFIDENCE
from tri_mesure.pipeline import readable_summary

router = APIRouter(tags=["cases"])


def _sla(s: Sla) -> SlaOut:
    return SlaOut(
        state=s.state, target_hours=s.target_hours, due_at=s.due_at, minutes_left=s.minutes_left
    )


def _call(c: LLMCall) -> LLMCallOut:
    return LLMCallOut(
        id=c.id,
        created_at=c.created_at,
        provider=c.gen_ai_system,
        model=c.gen_ai_request_model,
        prompt_version=c.prompt_version,
        input_tokens=c.gen_ai_usage_input_tokens,
        output_tokens=c.gen_ai_usage_output_tokens,
        cache_read_tokens=c.cache_read_tokens,
        cache_write_tokens=c.cache_write_tokens,
        cost_eur=c.cost_eur,
        latency_ms=c.latency_ms,
        schema_valid=c.schema_valid,
        stop_reason=c.stop_reason,
        error=c.error,
        masked_prompt=c.masked_prompt,
    )


def _queue_item(v: CaseView) -> QueueItem:
    e, s = v.email, v.suggestion
    return QueueItem(
        id=e.id,
        subject=e.subject,
        sender_email=e.sender_email,
        queued_at=e.queued_at,
        arm=e.arm,
        status=e.status,
        analysis_status=e.analysis_status,
        category=s.category if s else None,
        priority=s.priority if s else None,
        priority_reasons=s.priority_reasons if s else [],
        needs_check=bool(s and (s.needs_manual or s.confidence < MANUAL_REVIEW_CONFIDENCE)),
        sla=_sla(v.sla),
        holder=v.holder,
        event_id=e.event_id,
    )


def _detail(v: CaseView) -> CaseDetail:
    e = v.email
    return CaseDetail(
        id=e.id,
        received_at=e.received_at,
        queued_at=e.queued_at,
        closed_at=e.closed_at,
        sender_email=e.sender_email,
        subject=e.subject,
        body=e.body_raw,
        subject_masked=e.subject_masked,
        body_masked=e.body_masked,
        pii_counts=e.pii_counts,
        arm=e.arm,
        status=e.status,
        analysis_status=e.analysis_status,
        analysis_error=e.analysis_error,
        sla=_sla(v.sla),
        holder=v.holder,
        suggestion=SuggestionOut.model_validate(v.suggestion, from_attributes=True).model_copy(
            update={"summary": readable_summary(v.suggestion.summary, e.subject, e.body_raw)}
        )
        if v.suggestion
        else None,
        llm_calls=[_call(c) for c in v.calls],
        reviews=[ReviewOut.model_validate(r, from_attributes=True) for r in e.reviews],
    )


@router.post("/admin/seed", response_model=SeedOut, summary="Load synthetic demo e-mails")
async def seed(
    session: SessionDep,
    _: CanSeed,
    dataset: Annotated[str, Query(pattern="^(demo|dev|test)$")] = "demo",
) -> SeedOut:
    created, skipped = await intake.seed_demo(session, dataset)
    return SeedOut(created=created, skipped=skipped, queued_for_analysis=created)


@router.get("/cases", response_model=list[QueueItem], summary="The queue, most urgent first")
async def queue(session: SessionDep, _: CanReadCases) -> list[QueueItem]:
    return [_queue_item(v) for v in await casework.list_queue(session)]


@router.get(
    "/cases/next", response_model=NextCaseOut, summary="The single answer to « what do I do next? »"
)
async def next_case(session: SessionDep, user: CanReview) -> NextCaseOut:
    return NextCaseOut(id=await casework.next_case_id(session, actor_of(user)))


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(case_id: int, session: SessionDep, _: CanReadCases) -> CaseDetail:
    return _detail(await casework.get_case(session, case_id))


@router.post(
    "/cases/{case_id}/claim",
    response_model=CaseDetail,
    summary="Take the case (15-minute lease, renewed on each call)",
)
async def claim(case_id: int, session: SessionDep, user: CanReview) -> CaseDetail:
    return _detail(await casework.claim_case(session, case_id, actor_of(user)))


@router.post("/cases/{case_id}/release", status_code=204, summary="Give the case back")
async def release(case_id: int, session: SessionDep, user: CanReview) -> None:
    await casework.release_case(session, case_id, actor_of(user))


@router.post(
    "/cases/{case_id}/review",
    response_model=ReviewOut,
    summary="Record the human decision and close the case",
)
async def review(case_id: int, data: ReviewIn, session: SessionDep, user: CanReview) -> ReviewOut:
    command = ReviewCommand(
        category=FieldDecision(data.category.verdict, data.category.value),
        fields={k: FieldDecision(d.verdict, d.value) for k, d in data.fields.items()},
        reason_code=data.reason_code,
        manual=data.manual,
        seconds_to_decision=data.seconds_to_decision,
    )
    r = await casework.submit_review(session, case_id, command, actor_of(user))
    return ReviewOut.model_validate(r, from_attributes=True)


@router.get("/decisions/export", response_model=list[ReviewOut], summary="All decisions")
async def export_decisions(session: SessionDep, _: CanReadCases) -> list[ReviewOut]:
    return [
        ReviewOut.model_validate(r, from_attributes=True)
        for r in await casework.list_decisions(session)
    ]

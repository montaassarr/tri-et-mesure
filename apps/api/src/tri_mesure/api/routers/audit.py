"""Auditor: tamper-evident log, integrity check, processing register."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from tri_mesure.api.deps import CanAudit, SessionDep, SettingsDep
from tri_mesure.api.schemas import AuditEventOut, ChainReportOut
from tri_mesure.application import governance
from tri_mesure.audit.store import list_events, verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut], summary="Events, newest first (paginated)")
async def events(
    session: SessionDep,
    _: CanAudit,
    email_id: int | None = None,
    event_type: Annotated[str | None, Query(alias="type", max_length=40)] = None,
    actor_kind: Literal["human", "ai", "system"] | None = None,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEventOut]:
    rows = await list_events(
        session,
        email_id=email_id,
        event_type=event_type,
        actor_prefix=actor_kind,
        before_seq=before_seq,
        limit=limit,
    )
    return [AuditEventOut.model_validate(e, from_attributes=True) for e in rows]


@router.get("/verify", response_model=ChainReportOut, summary="Recompute every hash")
async def verify(session: SessionDep, _: CanAudit) -> ChainReportOut:
    report = await verify_chain(session)
    return ChainReportOut(**report.__dict__)


@router.get("/register", summary="Processing register (purpose, data, retention, recipients)")
async def register(session: SessionDep, settings: SettingsDep, _: CanAudit) -> dict[str, Any]:
    return await governance.processing_register(session, settings)


@router.get("/report", summary="Human-oversight report for a period (sealed, audited)")
async def oversight_report(
    session: SessionDep,
    settings: SettingsDep,
    user: CanAudit,
    days: Annotated[int, Query(ge=1, le=366)] = 30,
) -> dict[str, Any]:
    return await governance.oversight_report(session, settings, days, user.actor)

"""Team lead: dashboard and business assumptions."""

from typing import Any

from fastapi import APIRouter

from tri_mesure.api.deps import CanEditAssumptions, CanManageCrisis, CanPilot, SessionDep
from tri_mesure.api.schemas import AssumptionOut, AssumptionUpdate, CrisisIn
from tri_mesure.application import crisis, measurement

router = APIRouter(tags=["pilotage"])


@router.get("/pilotage", summary="Team dashboard: stock, deadlines, flow, measured AI value")
async def pilotage(session: SessionDep, _: CanPilot) -> dict[str, Any]:
    return await measurement.pilotage(session)


@router.get("/assumptions", response_model=list[AssumptionOut])
async def assumptions(session: SessionDep, _: CanPilot) -> list[AssumptionOut]:
    return [
        AssumptionOut.model_validate(a, from_attributes=True)
        for a in await measurement.list_assumptions(session)
    ]


@router.put("/assumptions/{key}", response_model=AssumptionOut)
async def update_assumption(
    key: str, data: AssumptionUpdate, session: SessionDep, user: CanEditAssumptions
) -> AssumptionOut:
    a = await measurement.update_assumption(session, key, data.value, user.actor)
    return AssumptionOut.model_validate(a, from_attributes=True)


# --- storm mode ----------------------------------------------------------------------


@router.get("/crisis", summary="The climate event in progress, if any, with live figures")
async def current_crisis(session: SessionDep, _: CanPilot) -> dict[str, Any] | None:
    event = await crisis.active_event(session)
    return await crisis.event_report(session, event) if event else None


@router.post("/crisis", summary="Declare a climate event (simulated burst of e-mails)")
async def start_crisis(
    data: CrisisIn, session: SessionDep, user: CanManageCrisis
) -> dict[str, Any]:
    event = await crisis.start_event(session, data.name, data.kind, data.volume, user.actor)
    return await crisis.event_report(session, event)


@router.post("/crisis/{event_id}/end", summary="Close the climate event")
async def end_crisis(event_id: int, session: SessionDep, user: CanManageCrisis) -> dict[str, Any]:
    event = await crisis.end_event(session, event_id, user.actor)
    return await crisis.event_report(session, event)

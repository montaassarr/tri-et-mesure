"""Health, reference data and Prometheus metrics."""

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from tri_mesure import __version__
from tri_mesure.api.deps import SessionDep, SettingsDep, UserDep
from tri_mesure.api.schemas import FieldGroup, Health, Meta
from tri_mesure.application.casework import REASON_CODES
from tri_mesure.domain.casework import SLA_HOURS
from tri_mesure.domain.schemas import FIELD_GROUPS, FIELD_LABELS
from tri_mesure.domain.taxonomy import CATEGORY_LABELS, DAMAGE_LABELS, SENDER_LABELS

router = APIRouter(tags=["system"])


@router.get("/health/live", summary="Liveness: the process answers")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health", response_model=Health, summary="Readiness: database and worker")
async def ready(request: Request, session: SessionDep, settings: SettingsDep) -> Health:
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    worker = getattr(request.app.state, "worker", None)
    if not settings.worker_enabled:
        worker_state = "disabled"
    else:
        worker_state = "running" if worker is not None and worker.running else "stopped"
    healthy = db_ok and worker_state != "stopped"
    return Health(
        status="ok" if healthy else "degraded",
        database=db_ok,
        worker=worker_state,
        worker_error=getattr(worker, "last_error", None),
        version=__version__,
    )


@router.get("/meta", response_model=Meta, summary="Labels and reference data for the UI")
async def meta(_: UserDep) -> Meta:
    return Meta(
        categories=CATEGORY_LABELS,
        senders=SENDER_LABELS,
        damages=DAMAGE_LABELS,
        fields=FIELD_LABELS,
        field_groups=[FieldGroup(label=label, fields=fields) for label, fields in FIELD_GROUPS],
        reason_codes=REASON_CODES,
        sla_targets_hours=SLA_HOURS,
    )


@router.get("/ops/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    # In production, expose this only on the internal network (scraped by Prometheus).
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

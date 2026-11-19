"""AI team: configuration, offline evaluation, production quality, analysis queue."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks

from tri_mesure.api.deps import CanConfigure, CanReadEval, CanRunEval, SessionDep, SettingsDep
from tri_mesure.api.schemas import (
    AIConfigIn,
    AIConfigOut,
    AlertOut,
    ChampionIn,
    CountOut,
    EvalRunIn,
    EvalRunOut,
    SourceCreated,
    SourceIn,
    SourceUpdate,
)
from tri_mesure.application import (
    ai_config,
    analysis,
    evaluation_jobs,
    measurement,
    monitoring,
    sources,
)
from tri_mesure.db.session import get_sessionmaker
from tri_mesure.llm.pricing import PRICES
from tri_mesure.llm.prompts import available_versions
from tri_mesure.settings import Settings

router = APIRouter(prefix="/ai", tags=["ai"])

KNOWN_MODELS = {
    "rules": ["rules-v1"],
    "anthropic": ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"],
    "openai_compat": [],
}


async def _config_out(session: SessionDep, settings: Settings) -> AIConfigOut:
    cfg = await ai_config.effective_config(session, settings)
    return AIConfigOut(
        provider=cfg.provider,
        model=cfg.model,
        prompt_version=cfg.prompt_version,
        daily_budget_eur=cfg.daily_budget_eur,
        spent_today_eur=round(await ai_config.spent_today_eur(session), 6),
        overridden=cfg.overridden,
        providers_available=ai_config.provider_availability(settings),
        prompt_versions=available_versions(),
        known_models=KNOWN_MODELS | {"openai_compat": [settings.openai_compat_model]},
        prices_usd_per_mtok={
            k: {"input": p.input_usd, "output": p.output_usd} for k, p in PRICES.items()
        },
        queue_depth=await analysis.queue_depth(session),
    )


@router.get("/config", response_model=AIConfigOut)
async def get_config(session: SessionDep, settings: SettingsDep, _: CanReadEval) -> AIConfigOut:
    return await _config_out(session, settings)


@router.put("/config", response_model=AIConfigOut, summary="Change model (audited)")
async def put_config(
    data: AIConfigIn, session: SessionDep, settings: SettingsDep, user: CanConfigure
) -> AIConfigOut:
    await ai_config.update_config(
        session, settings, user.actor, data.provider, data.model, data.prompt_version
    )
    return await _config_out(session, settings)


@router.post(
    "/reanalyze-open",
    response_model=CountOut,
    summary="Send open cases back to the worker (after a model change)",
)
async def reanalyze(session: SessionDep, user: CanConfigure) -> CountOut:
    return CountOut(count=await analysis.request_reanalysis(session, user.actor))


@router.post(
    "/process",
    response_model=CountOut,
    summary="Drain the analysis queue now (ops / tests; the worker does it anyway)",
)
async def process(settings: SettingsDep, _: CanConfigure) -> CountOut:
    return CountOut(count=await analysis.process_pending(settings, get_sessionmaker()))


@router.get("/quality", summary="How handlers judged AI suggestions in production")
async def quality(session: SessionDep, _: CanReadEval) -> dict[str, Any]:
    return await measurement.production_quality(session)


@router.post("/eval-runs", response_model=EvalRunOut, summary="Launch an offline evaluation")
async def start_eval(
    data: EvalRunIn,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    user: CanRunEval,
) -> EvalRunOut:
    run = await evaluation_jobs.create_run(
        session, settings, user.actor, data.provider, data.model, data.dataset, data.prompt_version
    )
    background.add_task(evaluation_jobs.execute_run, run.id, settings, get_sessionmaker())
    return EvalRunOut.model_validate(run, from_attributes=True)


@router.get("/eval-runs", response_model=list[EvalRunOut])
async def list_evals(session: SessionDep, _: CanReadEval) -> list[EvalRunOut]:
    return [
        EvalRunOut.model_validate(r, from_attributes=True)
        for r in await evaluation_jobs.list_runs(session)
    ]


# --- control tower -------------------------------------------------------------------


@router.get("/sources", summary="Scoreboard of every AI source (champion and shadows)")
async def scoreboard(session: SessionDep, _: CanReadEval) -> list[dict[str, Any]]:
    return await sources.scoreboard(session)


@router.post("/sources", response_model=SourceCreated, summary="Plug in an external AI vendor")
async def create_source(data: SourceIn, session: SessionDep, user: CanConfigure) -> SourceCreated:
    source, api_key = await sources.create_source(session, data.name, user.actor)
    return SourceCreated(code=source.code, name=source.name, api_key=api_key)


@router.put("/sources/{code}", summary="Activate or deactivate a source (audited)")
async def update_source(
    code: str, data: SourceUpdate, session: SessionDep, user: CanConfigure
) -> dict[str, Any]:
    s = await sources.set_active(session, code, data.active, user.actor)
    return {"code": s.code, "active": s.active}


@router.put("/champion", summary="Choose which source handlers see (audited)")
async def set_champion(data: ChampionIn, session: SessionDep, user: CanConfigure) -> dict[str, str]:
    return {"champion": await sources.set_champion(session, data.source, user.actor)}


@router.get("/alerts", response_model=list[AlertOut], summary="Drift and health alerts")
async def alerts(session: SessionDep, settings: SettingsDep, _: CanReadEval) -> list[AlertOut]:
    return [AlertOut(**a) for a in await monitoring.compute_alerts(session, settings)]

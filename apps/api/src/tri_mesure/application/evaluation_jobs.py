"""Offline evaluation runs, launched from the AI team's screen and executed in the background."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tri_mesure.application.errors import Invalid
from tri_mesure.audit.store import append_event
from tri_mesure.db.models import EvalRun
from tri_mesure.evaluation.run_eval import evaluate, load_dataset
from tri_mesure.llm.gateway import Gateway, make_provider
from tri_mesure.llm.prompts import available_versions
from tri_mesure.settings import Settings


async def create_run(
    session: AsyncSession,
    settings: Settings,
    actor: str,
    provider: str,
    model: str | None,
    dataset: str,
    prompt_version: str,
) -> EvalRun:
    if prompt_version not in available_versions():
        raise Invalid(f"Version de prompt inconnue : {prompt_version}")
    p = make_provider(settings, provider, model)
    run = EvalRun(provider=p.name, model=p.model, prompt_version=prompt_version, dataset=dataset)
    session.add(run)
    await session.flush()
    await append_event(
        session, "eval.started", actor, {"run_id": run.id, "model": p.model, "dataset": dataset}
    )
    await session.commit()
    return run


async def execute_run(
    run_id: int, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with sessionmaker() as session:
        run = await session.get_one(EvalRun, run_id)
        try:
            gateway = Gateway(
                make_provider(settings, run.provider, run.model),
                usd_to_eur=settings.usd_to_eur,
                daily_budget_eur=settings.daily_budget_eur,
                prompt_version=run.prompt_version,
            )
            report = await evaluate(load_dataset(run.dataset), gateway)
            run.summary, run.report, run.status = report.summary(), report.to_dict(), "done"
        except Exception as e:  # shown to the AI team on the run's row
            run.status, run.error = "error", f"{type(e).__name__}: {e}"
        await session.commit()


async def list_runs(session: AsyncSession, limit: int = 50) -> list[EvalRun]:
    rows = await session.execute(select(EvalRun).order_by(EvalRun.id.desc()).limit(limit))
    return list(rows.scalars())

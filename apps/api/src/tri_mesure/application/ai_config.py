"""Effective AI configuration: environment defaults, overridden at runtime by the AI team.

Changing the model is a change to a production system, so it is validated (provider key
present, prompt version exists) and recorded in the audit log with before/after values.
"""

from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tri_mesure.application.errors import Invalid
from tri_mesure.audit.store import append_event
from tri_mesure.db.models import AppConfig, LLMCall, utcnow
from tri_mesure.llm.gateway import Gateway, make_provider
from tri_mesure.llm.prompts import DEFAULT_VERSION, available_versions
from tri_mesure.llm.rules_provider import MODEL as RULES_MODEL
from tri_mesure.settings import Settings

PROVIDERS = ("rules", "anthropic", "openai_compat")


@dataclass(frozen=True)
class AIConfig:
    provider: str
    model: str
    prompt_version: str
    daily_budget_eur: float
    overridden: bool  # True when the AI team changed it at runtime


def provider_availability(settings: Settings) -> dict[str, bool]:
    return {
        "rules": True,
        "anthropic": bool(settings.anthropic_api_key),
        "openai_compat": bool(settings.openai_compat_api_key),
    }


def default_model(provider: str, settings: Settings) -> str:
    if provider == "anthropic":
        return settings.llm_model
    if provider == "openai_compat":
        return settings.openai_compat_model
    return RULES_MODEL


async def effective_config(session: AsyncSession, settings: Settings) -> AIConfig:
    rows = {r.key: r.value for r in (await session.execute(select(AppConfig))).scalars()}
    provider = rows.get("provider", settings.llm_provider)
    model = rows.get("model") or default_model(provider, settings)
    if provider == "rules":
        model = RULES_MODEL
    return AIConfig(
        provider=provider,
        model=model,
        prompt_version=rows.get("prompt_version", DEFAULT_VERSION),
        daily_budget_eur=settings.daily_budget_eur,
        overridden=bool(rows),
    )


async def update_config(
    session: AsyncSession,
    settings: Settings,
    actor: str,
    provider: str,
    model: str | None,
    prompt_version: str,
) -> AIConfig:
    if provider not in PROVIDERS:
        raise Invalid(f"Fournisseur inconnu : {provider}")
    if not provider_availability(settings)[provider]:
        raise Invalid(f"Aucune clé API configurée pour « {provider} »")
    if prompt_version not in available_versions():
        raise Invalid(f"Version de prompt inconnue : {prompt_version}")
    chosen_model = (
        RULES_MODEL if provider == "rules" else (model or default_model(provider, settings))
    )

    before = await effective_config(session, settings)
    for key, value in (
        ("provider", provider),
        ("model", chosen_model),
        ("prompt_version", prompt_version),
    ):
        row = await session.get(AppConfig, key)
        if row is None:
            session.add(AppConfig(key=key, value=value, updated_by=actor))
        else:
            row.value, row.updated_by, row.updated_at = value, actor, utcnow()
    after = AIConfig(provider, chosen_model, prompt_version, settings.daily_budget_eur, True)
    await append_event(
        session,
        "config.changed",
        actor,
        {"from": _public(before), "to": _public(after)},
    )
    await session.commit()
    return after


def _public(config: AIConfig) -> dict[str, str]:
    data = asdict(config)
    return {k: str(data[k]) for k in ("provider", "model", "prompt_version")}


async def spent_today_eur(session: AsyncSession) -> float:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        await session.execute(
            select(func.coalesce(func.sum(LLMCall.cost_eur), 0.0)).where(
                LLMCall.created_at >= start
            )
        )
    ).scalar_one()
    return float(total or 0.0)


def build_gateway(session: AsyncSession, settings: Settings, config: AIConfig) -> Gateway:
    async def spent() -> float:
        return await spent_today_eur(session)

    return Gateway(
        make_provider(settings, config.provider, config.model),
        usd_to_eur=settings.usd_to_eur,
        daily_budget_eur=settings.daily_budget_eur,
        spent_today=spent,
        prompt_version=config.prompt_version,
    )

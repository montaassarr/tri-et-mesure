"""The single path every model call goes through.

Responsibilities: build the versioned prompt from *masked* text, enforce the daily budget,
retry once on a failed or invalid answer, fall back to the deterministic rules provider so
a case is never stuck, and return every attempt so the caller can write the cost ledger.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date

from tri_mesure.domain.schemas import Extraction
from tri_mesure.llm.anthropic_provider import AnthropicProvider
from tri_mesure.llm.base import LLMProvider, LLMResult, Prompt
from tri_mesure.llm.openai_compat_provider import OpenAICompatProvider
from tri_mesure.llm.pricing import cost_eur
from tri_mesure.llm.prompts import DEFAULT_VERSION, load_system_prompt
from tri_mesure.llm.rules_provider import RulesProvider
from tri_mesure.settings import Settings


def build_user_message(subject: str, masked_body: str, received: date) -> str:
    return (
        f"Date de réception : {received.isoformat()}\n"
        f"Objet : {subject}\n"
        f"--- E-MAIL ---\n{masked_body}"
    )


@dataclass
class Attempt:
    result: LLMResult
    prompt_version: str
    cost_eur: float | None


@dataclass
class GatewayOutcome:
    extraction: Extraction | None
    attempts: list[Attempt] = field(default_factory=list)
    used_fallback: bool = False
    manual_reason: str | None = None

    @property
    def final(self) -> Attempt:
        return self.attempts[-1]

    @property
    def total_cost_eur(self) -> float:
        return sum(a.cost_eur or 0.0 for a in self.attempts)


SpentToday = Callable[[], Awaitable[float]]


class Gateway:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        usd_to_eur: float,
        daily_budget_eur: float,
        spent_today: SpentToday | None = None,
        prompt_version: str = DEFAULT_VERSION,
        fallback: LLMProvider | None = None,
    ) -> None:
        self.provider = provider
        self.usd_to_eur = usd_to_eur
        self.daily_budget_eur = daily_budget_eur
        self.spent_today = spent_today
        self.prompt_version = prompt_version
        self.system = load_system_prompt(prompt_version)
        self.fallback = fallback if fallback is not None else RulesProvider()

    def _attempt(self, result: LLMResult) -> Attempt:
        return Attempt(
            result, self.prompt_version, cost_eur(result.model, result.usage, self.usd_to_eur)
        )

    async def suggest(self, subject: str, masked_body: str, received: date) -> GatewayOutcome:
        prompt = Prompt(
            self.prompt_version, self.system, build_user_message(subject, masked_body, received)
        )
        outcome = GatewayOutcome(extraction=None)

        over_budget = False
        if self.spent_today is not None and self.provider.name != "rules":
            over_budget = (await self.spent_today()) >= self.daily_budget_eur

        if not over_budget:
            for _ in range(2):  # one retry
                attempt = self._attempt(await self.provider.extract(prompt))
                outcome.attempts.append(attempt)
                if attempt.result.extraction is not None:
                    outcome.extraction = attempt.result.extraction
                    return outcome

        # Budget exhausted or two failures: deterministic fallback, flagged for a human.
        fallback = self._attempt(await self.fallback.extract(prompt))
        outcome.attempts.append(fallback)
        outcome.extraction = fallback.result.extraction
        outcome.used_fallback = True
        outcome.manual_reason = (
            "Budget journalier atteint : suggestion par règles"
            if over_budget
            else "Échec du modèle (2 tentatives) : suggestion par règles"
        )
        return outcome


def make_provider(
    settings: Settings, provider: str | None = None, model: str | None = None
) -> LLMProvider:
    name = provider or settings.llm_provider
    if name == "rules":
        return RulesProvider()
    if name == "anthropic":
        return AnthropicProvider(model or settings.llm_model, settings.anthropic_api_key)
    if name == "openai_compat":
        return OpenAICompatProvider(
            model or settings.openai_compat_model,
            settings.openai_compat_base_url,
            settings.openai_compat_api_key,
        )
    raise ValueError(f"Unknown provider: {name}")

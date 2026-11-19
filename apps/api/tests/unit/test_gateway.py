from datetime import date

from tri_mesure.domain.schemas import ExtractedFields, Extraction
from tri_mesure.llm.base import LLMResult, Prompt, Usage
from tri_mesure.llm.gateway import Gateway
from tri_mesure.pipeline import suggest

RECEIVED = date(2026, 11, 18)


class FakeProvider:
    name = "fake"
    model = "claude-haiku-5-5"  # priced model, so cost is computed

    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.calls: list[Prompt] = []

    async def extract(self, prompt: Prompt) -> LLMResult:
        self.calls.append(prompt)
        usage = Usage(input_tokens=1000, output_tokens=200)
        if len(self.calls) <= self.fail_times:
            return LLMResult(self.name, self.model, None, usage, 10, None, "schema_error")
        extraction = Extraction(
            category="declaration_sinistre",
            sender_type="assure",
            confidence=0.9,
            fields=ExtractedFields(numero_contrat="<CONTRAT_1>", fuite_active=True),
            evidence=[],
            summary="Dégât des eaux.",
        )
        return LLMResult(self.name, self.model, extraction, usage, 10, "end_turn")


def _gateway(provider: FakeProvider, spent: float = 0.0, budget: float = 1.0) -> Gateway:
    async def spent_today() -> float:
        return spent

    return Gateway(provider, usd_to_eur=1.0, daily_budget_eur=budget, spent_today=spent_today)


async def test_prompt_contains_only_masked_text() -> None:
    provider = FakeProvider()
    await suggest(
        _gateway(provider), "Sinistre", "Contrat CT12345678, tél 06 12 34 56 78.", RECEIVED
    )
    sent = provider.calls[0].user
    assert "CT12345678" not in sent
    assert "06 12 34 56 78" not in sent
    assert "<CONTRAT_1>" in sent


async def test_fields_are_unmasked_and_priority_computed() -> None:
    s = await suggest(_gateway(FakeProvider()), "Sinistre", "Contrat CT12345678.", RECEIVED)
    assert s.fields["numero_contrat"] == "CT12345678"
    assert s.priority.priority == "urgente"
    assert not s.needs_manual


async def test_cost_is_computed_from_usage() -> None:
    s = await suggest(_gateway(FakeProvider()), "x", "y", RECEIVED)
    # 1000 * 0.10/1M + 200 * 0.50/1M = 0.0002 USD, rate 1.0
    assert abs(s.outcome.total_cost_eur - 0.0002) < 1e-9


async def test_one_retry_then_success() -> None:
    provider = FakeProvider(fail_times=1)
    s = await suggest(_gateway(provider), "x", "y", RECEIVED)
    assert len(provider.calls) == 2
    assert not s.outcome.used_fallback


async def test_two_failures_fall_back_to_rules_and_flag_manual() -> None:
    provider = FakeProvider(fail_times=5)
    s = await suggest(_gateway(provider), "Résiliation", "Je souhaite résilier.", RECEIVED)
    assert len(provider.calls) == 2
    assert s.outcome.used_fallback
    assert s.needs_manual
    assert s.outcome.final.result.provider == "rules"


async def test_budget_exhausted_skips_model() -> None:
    provider = FakeProvider()
    s = await suggest(_gateway(provider, spent=5.0, budget=1.0), "x", "y", RECEIVED)
    assert provider.calls == []
    assert s.outcome.used_fallback
    assert s.manual_reason is not None and "Budget" in s.manual_reason

"""Per-model token prices, used to compute the euro cost of every call.

Prices are USD per million tokens. Claude prices are Anthropic first-party list prices
(checked 2026-11-03; Haiku 5.5 price applies to prompts up to 100K tokens). Third-party
prices come from public price lists and may be out of date — they are shown in the UI as
an assumption. Re-check before quoting any cost figure.
"""

from dataclasses import dataclass

from tri_mesure.llm.base import Usage


@dataclass(frozen=True)
class Price:
    input_usd: float
    output_usd: float
    cache_write_multiplier: float = 1.25
    cache_read_multiplier: float = 0.1


PRICES: dict[str, Price] = {
    # Anthropic
    "claude-opus-5-5": Price(4.00, 20.00),
    "claude-sonnet-5-5": Price(2.00, 10.00),
    "claude-haiku-5-5": Price(0.10, 0.50),
    # Groq (OpenAI-compatible) — aggregator figures, unverified
    "llama-3.1-8b-instant": Price(0.05, 0.08, 1.0, 1.0),
    # Mistral — aggregator figures, unverified
    "mistral-small-latest": Price(0.15, 0.60, 1.0, 1.0),
    # Deterministic rules: free
    "rules-v1": Price(0.0, 0.0, 1.0, 1.0),
}


def cost_usd(model: str, usage: Usage) -> float | None:
    """Cost of one call in USD, or None when the model has no known price."""
    price = PRICES.get(model)
    if price is None:
        return None
    per_token_in = price.input_usd / 1_000_000
    per_token_out = price.output_usd / 1_000_000
    return (
        usage.input_tokens * per_token_in
        + usage.cache_write_tokens * per_token_in * price.cache_write_multiplier
        + usage.cache_read_tokens * per_token_in * price.cache_read_multiplier
        + usage.output_tokens * per_token_out
    )


def cost_eur(model: str, usage: Usage, usd_to_eur: float) -> float | None:
    usd = cost_usd(model, usage)
    return None if usd is None else usd * usd_to_eur

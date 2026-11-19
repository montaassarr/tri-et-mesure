"""Claude provider: official Anthropic SDK with structured outputs.

`messages.parse(output_format=Extraction)` constrains the response to the Pydantic schema
and returns a validated object. The frozen system prompt is marked for prompt caching; if
it is shorter than the model's minimum cacheable prefix the cache simply stays unused,
which the cost ledger shows (cache_read_tokens = 0).
"""

import time
from typing import Any

import anthropic

from tri_mesure.domain.schemas import Extraction
from tri_mesure.llm.base import LLMResult, Prompt, Usage

# Models that accept output_config.effort. Extraction is a simple task: low effort.
_EFFORT_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None, timeout_s: float = 60.0) -> None:
        self.model = model
        # api_key=None lets the SDK resolve ANTHROPIC_API_KEY or an `ant auth login` profile.
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s, max_retries=2)

    async def extract(self, prompt: Prompt) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "system": [
                {"type": "text", "text": prompt.system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": prompt.user}],
            "output_format": Extraction,
        }
        if self.model in _EFFORT_MODELS:
            kwargs["output_config"] = {"effort": "low"}

        started = time.perf_counter()
        try:
            response = await self._client.messages.parse(**kwargs)
        except anthropic.RateLimitError as e:
            return self._error(started, f"rate_limited: {e.message}")
        except anthropic.APIStatusError as e:
            return self._error(started, f"api_error_{e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            return self._error(started, "connection_error")
        except Exception as e:  # invalid JSON after truncation, validation errors, ...
            return self._error(started, f"parse_error: {type(e).__name__}: {e}")

        latency_ms = int((time.perf_counter() - started) * 1000)
        u = response.usage
        usage = Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=u.cache_read_input_tokens or 0,
            cache_write_tokens=u.cache_creation_input_tokens or 0,
        )
        raw_text = next((b.text for b in response.content if b.type == "text"), None)

        if response.stop_reason == "refusal":
            return LLMResult(
                self.name, self.model, None, usage, latency_ms, "refusal", "refusal", raw_text
            )
        if response.stop_reason == "max_tokens":
            return LLMResult(
                self.name, self.model, None, usage, latency_ms, "max_tokens", "truncated", raw_text
            )

        parsed = response.parsed_output
        if parsed is None:
            return LLMResult(
                self.name,
                self.model,
                None,
                usage,
                latency_ms,
                response.stop_reason,
                "no_parsed_output",
                raw_text,
            )
        return LLMResult(
            self.name,
            self.model,
            parsed.normalise(),
            usage,
            latency_ms,
            response.stop_reason,
            None,
            raw_text,
        )

    def _error(self, started: float, message: str) -> LLMResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResult(self.name, self.model, None, Usage(), latency_ms, None, message)

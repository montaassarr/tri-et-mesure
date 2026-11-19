"""Any OpenAI-compatible chat endpoint: Groq (free tier), Mistral, Ollama, Azure OpenAI.

Uses JSON mode plus the schema in the prompt (JSON-schema enforcement varies between
these providers), then validates with Pydantic. Schema failures are reported, not hidden:
they feed the "schema-valid rate" on the evaluation page.
"""

import json
import time

import openai
from pydantic import ValidationError

from tri_mesure.domain.schemas import Extraction
from tri_mesure.llm.base import LLMResult, Prompt, Usage

_SCHEMA_HINT = (
    "\n\n## Format de réponse\n\nRéponds uniquement par un objet JSON conforme à ce schéma :\n"
)


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, model: str, base_url: str, api_key: str | None, timeout_s: float = 60.0):
        self.model = model
        self._client = openai.AsyncOpenAI(
            base_url=base_url, api_key=api_key or "not-needed", timeout=timeout_s, max_retries=2
        )
        self._schema = json.dumps(Extraction.model_json_schema(), ensure_ascii=False)

    async def extract(self, prompt: Prompt) -> LLMResult:
        started = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt.system + _SCHEMA_HINT + self._schema},
                    {"role": "user", "content": prompt.user},
                ],
                response_format={"type": "json_object"},
                max_tokens=2048,
            )
        except openai.RateLimitError as e:
            return self._error(started, f"rate_limited: {e}")
        except openai.APIStatusError as e:
            return self._error(started, f"api_error_{e.status_code}: {e.message}")
        except openai.APIConnectionError:
            return self._error(started, "connection_error")

        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = Usage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        choice = response.choices[0]
        raw = choice.message.content or ""
        try:
            extraction = Extraction.model_validate_json(raw).normalise()
        except ValidationError as e:
            return LLMResult(
                self.name,
                self.model,
                None,
                usage,
                latency_ms,
                choice.finish_reason,
                f"schema_error: {e.error_count()} error(s)",
                raw,
            )
        return LLMResult(
            self.name, self.model, extraction, usage, latency_ms, choice.finish_reason, None, raw
        )

    def _error(self, started: float, message: str) -> LLMResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResult(self.name, self.model, None, Usage(), latency_ms, None, message)

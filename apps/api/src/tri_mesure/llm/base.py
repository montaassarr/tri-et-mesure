"""Provider-agnostic contract for model calls."""

from dataclasses import dataclass, field
from typing import Protocol

from tri_mesure.domain.schemas import Extraction


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class LLMResult:
    provider: str
    model: str
    extraction: Extraction | None
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    stop_reason: str | None = None
    error: str | None = None
    raw_text: str | None = None

    @property
    def schema_valid(self) -> bool:
        return self.extraction is not None


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    user: str


class LLMProvider(Protocol):
    name: str
    model: str

    async def extract(self, prompt: Prompt) -> LLMResult:
        """Return an Extraction (or an error) for one e-mail. Must not raise."""
        ...

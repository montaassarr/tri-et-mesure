# 0002 — One provider-agnostic gateway, with a rules fallback

**Status:** accepted · 2026-11-18

## Context

Inside a company the model would be reached through internal LLM APIs. For this prototype
the options are Claude, a free OpenAI-compatible tier (Groq), or no model at all. The demo
must never break in front of an interviewer.

## Decision

- Every call goes through `llm/gateway.py`, behind a single `LLMProvider.extract(prompt)`
  contract.
- Three implementations:
  - Claude: official SDK, structured outputs on the `Extraction` Pydantic schema;
  - any OpenAI-compatible endpoint: JSON mode plus Pydantic validation;
  - deterministic rules.
- The gateway enforces a daily € budget, retries once, then falls back to rules and flags
  the case for a human.

## Consequences

- Switching provider is a configuration change, not a code change.
- Models can be compared on the same evaluation set for accuracy per euro.
- The rules provider is also the free, deterministic CI evaluation gate.

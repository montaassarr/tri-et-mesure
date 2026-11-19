# 0007 — The AI team changes the model at runtime, and every change is audited

**Status:** accepted · 2026-11-18

## Context

Changing the model or the prompt changes what handlers see, which makes it a change to
a production system. Doing it by editing environment variables and redeploying is slow,
and it leaves no business-level trace.

## Decision

- Defaults come from environment variables. Runtime overrides (`provider`, `model`,
  `prompt_version`) live in `app_config`.
- `PUT /api/ai/config` requires `config.write`. It validates that the vendor key exists
  and that the prompt version exists, then writes a `config.changed` audit event with the
  before and after values.
- Prompts are immutable files (`llm/prompts/vN.md`). A change means a new version, which
  is evaluated offline first, then switched.
- « Réanalyser les dossiers ouverts » sends undecided cases back to the worker with the
  new configuration.

## Consequences

- Rolling back is one click and is traced as well.
- Production quality is reported per model and prompt version, so a regression shows
  up quickly.

# 0008 — A vendor-neutral control tower: champion, shadows, unbiased scoring

**Status:** accepted · 2026-11-19

## Context

Insurers already buy AI that sorts mail, drafts replies and routes cases, from several
vendors, and they also build their own. Each vendor reports its own success. What is
missing is a **neutral referee**: on the same cases, which AI actually helps, at what
cost, and is it getting worse? Building one more triage AI would not answer that.

## Decision

- Every AI system is a **source** (`ai_sources`). Ours is `interne`. External vendors
  are registered by the AI team and receive an API key; only its SHA-256 is stored.
- Integration contract, two calls:
  - `GET /api/ingest/cases`: open cases, **masked text only**;
  - `POST /api/ingest/cases/{id}/suggestion`: the same schema as our own model's output.
  Vendors never see identities, other vendors' answers or human decisions. Late proposals
  on closed cases are refused.
- One source is the **champion**: handlers see its proposal. All others run in
  **shadow mode** on the same cases. Promotion is one click and is audited.
- Each human decision is attributed to the suggestion that was actually shown.
- **Unbiased score.** Handlers tend to accept what they are shown, which favours the
  champion. Sources are therefore also scored on **control-arm cases**, where the human
  decided without seeing any AI. On synthetic data, ground truth is a third check.

## Consequences

- A new vendor can be trialled on real traffic with zero risk, then promoted on evidence.
- The same scoreboard compares our own model, a vendor's model, and plain rules.
- A worse vendor (simulate it with `pnpm vendor -- --noise 0.4`) shows up in the scores,
  and in the drift alarm once promoted.

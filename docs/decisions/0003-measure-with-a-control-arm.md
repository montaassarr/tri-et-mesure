# 0003 — Measure the gain with a control arm

**Status:** accepted · 2026-11-18

## Context

"The AI saves time" means nothing without a baseline. Projected savings built on assumed
handling times are not evidence.

## Decision

- Each e-mail is assigned deterministically to an **AI** arm or a **control** arm (50/50,
  based on a hash of its id).
- Control cases show no suggestion in the queue or the case view until closed.
- Time to decision is recorded for both arms.
- Accuracy against the synthetic ground truth is computed for both arms.
- Business assumptions (volume, baseline minutes, hourly cost) are stored separately and
  always labelled « hypothèse ».

## Consequences

- The dashboard can show a small but real with/without comparison, in the shape of a
  "deployed vs not deployed" KPI.
- The estimate is only shown once each arm has at least 5 cases. It always shows its
  formula and a non-extrapolation warning.

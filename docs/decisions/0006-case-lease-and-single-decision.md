# 0006 — A case is leased to one handler; one decision per case

**Status:** accepted · 2026-11-18

## Context

Several handlers work the same queue. Without coordination, two of them open the same
urgent case, both spend time on it, and the second decision overwrites the first.

## Decision

- Opening a case takes a **lease** of 15 minutes (`assigned_to`, `assigned_at`), renewed
  every 5 minutes while the page is open. Others see « Pris en charge par X » and get a
  409 if they try to decide.
- A lease, not a lock: if the handler leaves, the case comes back by itself.
- The database enforces **one review per case** (unique `reviews.email_id`). Even if two
  requests race past the application checks, the second gets a 409.
- « Traiter le dossier suivant » returns the most urgent open case that is free or already
  yours.

## Consequences

- No duplicate work, no lost decisions, and nothing to unlock manually.
- `case.claimed` and `case.released` are audited, so who held a case and when can be
  reconstructed.

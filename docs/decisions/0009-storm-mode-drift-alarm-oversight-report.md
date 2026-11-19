# 0009 — Storm mode, drift alarm and oversight report

**Status:** accepted · 2026-11-19

## Context

Three moments decide whether AI in claims is trusted:

1. **The day of a storm**, when volume multiplies and the team is under pressure.
2. **The week the model quietly gets worse.** The model doesn't crash; it just becomes
   less accurate.
3. **The audit**, when someone asks "prove that humans were in control".

## Decision

- **Storm mode.** The team lead declares a climate event (hail, storm or flood) and its
  volume. A burst of labelled synthetic e-mails arrives through the **normal** path:
  masking, worker, rules, lease and decision. Storm mode is therefore a load test of the
  real system. The live card shows:
  - stock, urgent and late cases;
  - closings in the last hour;
  - **estimated time to clear the backlog**;
  - median handling time with and without AI during the event.
- **Drift alarm.** On the champion's decisions, category acceptance over the last 10 is
  compared with the 30 before; a drop of 15 points or more raises a critical alert. The
  module also raises alerts when:
  - a field is corrected 40 % of the time or more;
  - rules fallbacks reach 20 % or more;
  - analyses fail;
  - the queue backs up;
  - the budget is nearly spent.
  Each alert says what to do, and Prometheus exposes `tm_ai_acceptance_rate{source}`.
- **Oversight report.** For the period, the auditor gets:
  - who decided, how many decisions were made with and without AI;
  - corrections and rejection reasons;
  - which AI systems and versions were used and shown;
  - every configuration change;
  - privacy figures;
  - the integrity check.
  It is **sealed** with the current head of the hash chain, and generating it is itself
  audited. It is printable to PDF.

## Consequences

- The demo tells a full story in three minutes: storm → triage under pressure → measured
  gain → vendor comparison → drift alert → sealed report.
- The thresholds are simple and explainable, and can be tuned in `application/monitoring.py`.

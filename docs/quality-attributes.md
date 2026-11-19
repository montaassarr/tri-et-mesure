# Quality attributes

For each quality: the target, how the code meets it, and the proof you can run.

| Quality | Target | How | Proof |
|---|---|---|---|
| **Human oversight** | No case closed without an authenticated human | Review endpoint requires `cases.review` and the lease; the AI only writes suggestions | `test_take_decide_close_with_audit_trail` |
| **Traceability** | Every action has an author and cannot be altered silently | Hash-chained audit log; DB trigger refuses UPDATE / DELETE / TRUNCATE | CI job "append-only trigger works"; `test_audit_chain.py` |
| **Privacy** | No identifying data reaches the model | Masking before every call; only masked prompts stored; raw text purged after N days | `test_prompt_contains_only_masked_text`; register screen |
| **Correctness under concurrency** | Two handlers never decide twice; two workers never analyse twice | 15-min lease + unique `reviews.email_id`; `FOR UPDATE SKIP LOCKED` | `test_take_decide_close…` (409); `test_process_pending_analyses_everything_once` |
| **Resilience** | A model outage never stops the team | Async intake; retry once; rules fallback; stale-claim recovery; graceful worker shutdown | `test_two_failures_fall_back…`, `test_failures_are_retried…`, `test_stop_is_graceful…` |
| **Cost control** | Spend is bounded and visible | Daily € budget in the gateway; every call priced in the ledger; Prometheus `tm_llm_cost_eur_total` | `test_budget_exhausted_skips_model`; AI screen |
| **Measurable value** | The gain is measured, not assumed | Control arm hidden from AI; medians compared; assumptions stored and labelled | `test_pilotage_measures_the_gain…` |
| **Model quality** | A worse prompt cannot ship | Labelled synthetic set; CI fails below macro-F1 0.75 | CI step "Evaluation gate" |
| **Vendor neutrality** | Any AI can be compared on the same cases, without bias | Champion and shadow sources; scoring on control-arm cases; vendors get masked text only | `test_control_tower.py` |
| **Early warning** | A quietly worse model is noticed in days, not months | Acceptance drift alarm and field-correction alerts | `test_drift_alert_fires…` |
| **Peak load** | A storm does not break the flow | Async queue, priorities, leases; storm mode shows the time to clear the backlog | `test_storm_mode…` |
| **Accountability** | Human oversight can be proven for any period | Sealed, audited oversight report | `test_oversight_report_is_sealed_and_audited` |
| **Security** | Least privilege, no default secrets in prod | JWT with role claims; permission per route; startup refuses the dev secret in prod; secret ≥ 32 chars | `test_each_role_only_reaches_its_own_screens`; `test_empty_or_weak_auth_secret…` |
| **Observability** | Any incident can be traced from UI to log line | Request id on every response and log line; JSON logs; Prometheus metrics; RFC 9457 errors show the request id | `test_unauthenticated_request_gets_problem_details` |
| **Maintainability** | Layers cannot leak | Clean layering enforced by import-linter; strict mypy; ruff | CI steps "Architecture contracts", "Type check" |
| **Portability** | Same behaviour on SQLite (dev) and PostgreSQL (prod) | UTC-safe timestamp type; same suite runs on both | CI job "tests on PostgreSQL" |
| **Usability** | A handler knows what to do next without training | One primary action per screen; "Traiter le dossier suivant"; Ctrl + Entrée; details hidden by default | [UX notes](ux.md) |
| **Accessibility** | Keyboard and screen-reader friendly | Status in words, not colour only; labelled inputs; focusable rows; `aria-*` on tabs and radios | Manual check; ESLint |

## Known limits

- Postal addresses are not masked. A French NER model (for example Presidio with spaCy)
  would add that.
- The demo login has no password; production would use OIDC (see ADR 0004).
- The in-process worker shares the API's resources. Above a few thousand e-mails a day,
  run it as its own process; the code is ready for it.
- All data is synthetic. Measured numbers come from a small pilot and must not be
  extrapolated.

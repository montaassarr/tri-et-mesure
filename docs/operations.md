# Operations runbook

## Run

| Goal | Command |
|---|---|
| Database | `docker compose up -d db` |
| Migrate | `pnpm db:migrate` |
| Dev (API :8000 + web :5173) | `pnpm dev` |
| Everything in containers (:8080) | `docker compose up --build` |
| All checks | `pnpm lint && pnpm test` |
| Evaluate a model | `pnpm eval -- --provider anthropic --model claude-haiku-5-5` |
| Simulate an external AI vendor | `pnpm vendor -- --key tm_… [--noise 0.4] [--engine groq] [--loop]` |

## Configuration

All settings are environment variables, see [`.env.example`](../.env.example). The AI team
can override the provider, model and prompt at runtime from the « Modèle IA » screen. Each
override is stored in `app_config` and audited.

## Health and signals

| Endpoint | Meaning | Use |
|---|---|---|
| `GET /api/health/live` | The process answers | Container liveness probe |
| `GET /api/health` | Database reachable and worker running | Readiness probe, load balancer |
| `GET /api/ops/metrics` | Prometheus text format | Scraped every 15 s |

| Metric | Alert when | Likely cause |
|---|---|---|
| `tm_analysis_queue_depth` | > 50 for 10 min | Model slow or down, worker stopped |
| `rate(tm_llm_calls_total{outcome!="ok"}[5m])` | > 20 % of calls | Vendor errors, schema changes, bad prompt |
| `increase(tm_llm_cost_eur_total[1d])` | > 80 % of `DAILY_BUDGET_EUR` | Volume spike or model switched to a bigger one |
| `tm_http_requests_total{status=~"5.."}` | > 1 % | Bug, database issue; search logs by `request_id` |
| `tm_ai_acceptance_rate{source}` | drops 15 points | Model drift: compare with a shadow source, roll back or switch champion |

The same checks appear in the UI as alerts (« Contrôle des IA » screen), each with the
action to take.

Every response carries `X-Request-ID`. Every error body (RFC 9457) contains `request_id`.
The UI shows it next to error messages, so a screenshot from a user is enough to find
the log line.

## Incidents

| Symptom | Check | Fix |
|---|---|---|
| Cases stuck on « Analyse IA… » | `/api/health` → `worker` | Restart the API. Claims stale for more than 5 min are picked up automatically. |
| « Analyse échouée » on many cases | `analysis_error` on the case, logs `analysis_failed` | Fix the cause (key, quota), then « Réanalyser les dossiers ouverts » |
| All suggestions come from rules | AI screen: budget bar, provider | Budget reached (resets at midnight UTC) or key missing |
| « Chaîne rompue » in the journal | `/api/audit/verify` → `first_broken_seq` | Security incident: freeze the database, compare with exported hashes |
| A handler cannot take a case | Queue: lock badge | Another handler holds the lease. It expires after 15 min without activity. |

## Deploying a new prompt or model

1. Add `llm/prompts/vN.md`. Never edit a published version.
2. Run the offline evaluation on the `test` set and compare with the current version.
3. If it is better, switch from the AI screen (audited), then re-analyse the open cases.
4. Watch « Qualité en production » for a few days. Roll back the same way if needed.

# 0005 — Analysis runs asynchronously, outside the request

**Status:** accepted · 2026-11-18

## Context

Loading 80 e-mails used to call the model 80 times inside one HTTP request: about 2 to
3 minutes with a real LLM, an HTTP timeout, and a frozen UI. In production, a slow
vendor must never stop the intake of mail.

## Decision

- Intake only stores, masks and marks `analysis_status = pending`.
- A worker claims batches with `SELECT … FOR UPDATE SKIP LOCKED`, then runs the
  pipeline. On error it retries up to `WORKER_MAX_ATTEMPTS` times and then marks the
  e-mail `failed` (audited). A `running` claim older than 5 minutes is taken over, which
  recovers from a crashed worker.
- The worker runs inside the API process as an asyncio task. Shutdown is graceful: it
  finishes the current batch, with a 30-second cap.
- The UI polls while e-mails are pending and shows « Analyse IA… ».

## Alternatives considered

- **Celery / RQ with Redis**: one more piece of infrastructure, unnecessary at this volume.
- **Kafka**: kept for a later step (intake service with an outbox).

## Consequences

- Intake latency no longer depends on the model.
- Several workers or API replicas can run safely in parallel.
- Moving the worker to its own container is a deployment change, not a code change.

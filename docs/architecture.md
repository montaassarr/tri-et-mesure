# Architecture

Four levels of zoom (C4), then the two flows and the data model. One rule throughout:
**the AI proposes, a human decides, everything is measured and traced.**

## 1. Context

```mermaid
flowchart LR
    S[Senders<br/>assuré, agent, garage, expert] -->|e-mail| T[Tri & Mesure]
    H[Gestionnaire · Responsable<br/>Auditeur · Équipe IA] -->|browser| T
    T -->|masked text only| V[(LLM vendor<br/>Claude / OpenAI-compatible)]
    X[External AI vendors] -->|API key · masked text in,<br/>proposals out| T
    T -->|metrics| O[(Prometheus)]
```

## 2. Containers

```mermaid
flowchart LR
    B[Web app<br/>React 19 · TypeScript · Vite<br/>TanStack Router + Query] -->|HTTPS + JWT<br/>typed client from OpenAPI| A
    subgraph A[API process · FastAPI]
        direction TB
        R[HTTP routers] --> U[Use cases]
        W[Analysis worker<br/>asyncio task] --> U
    end
    A --> D[(PostgreSQL 16<br/>cases · ledger · audit chain)]
    A -->|masked prompt| L[(LLM vendor)]
```

The worker runs inside the API process for simplicity. It claims work with
`FOR UPDATE SKIP LOCKED`, so it can be moved to its own container, or scaled to N
replicas, without code changes ([ADR 0005](decisions/0005-asynchronous-analysis-worker.md)).

## 3. Components (inside the API)

Dependencies point **inwards only**. [import-linter](../apps/api/pyproject.toml) checks
this in CI, and the build fails if a layer leaks.

```mermaid
flowchart TB
    subgraph api["api/ · HTTP only"]
        routers[routers/*] --- security[security · JWT, permissions]
        routers --- errors[errors · RFC 9457]
        routers --- mw[middleware · request id, logs, metrics]
    end
    subgraph application["application/ · use cases, no HTTP"]
        intake --- analysis --- casework
        measurement --- governance --- ai_config --- evaluation_jobs
    end
    subgraph adapters["adapters"]
        llm[llm/ · gateway + providers]
        pii[pii/ · masker]
        audit[audit/ · hash chain]
        db[db/ · SQLAlchemy models]
    end
    subgraph domain["domain/ · pure rules, no I/O"]
        taxonomy --- schemas --- priority_rules --- casework_rules[casework · SLA, lease] --- roles
    end
    api --> application --> adapters --> domain
    application --> domain
```

| Layer | May import | Must not import | Checked by |
|---|---|---|---|
| `domain` | stdlib, pydantic | anything else in the app, FastAPI, SQLAlchemy, vendor SDKs | import-linter |
| `application` | domain, adapters | `api`, FastAPI, Starlette | import-linter |
| adapters (`llm`, `pii`, `audit`) | domain | `api`, `application` | import-linter |
| vendor SDKs (`anthropic`, `openai`) | only `llm/*_provider.py` | everywhere else | import-linter |

## 4. Flows

### An e-mail, from arrival to decision

```mermaid
sequenceDiagram
    autonumber
    participant In as Réception
    participant DB as PostgreSQL
    participant W as Worker
    participant G as LLM gateway
    participant H as Gestionnaire
    In->>DB: store e-mail, masked copy, status=pending (audit: email.received, pii.masked)
    W->>DB: claim batch (FOR UPDATE SKIP LOCKED)
    W->>G: masked prompt (versioned)
    G-->>W: structured extraction (or retry, or rules fallback)
    W->>DB: suggestion + cost ledger (audit: ai.suggested, priority.computed)
    H->>DB: GET /cases/next → claim (15-min lease, audit: case.claimed)
    H->>DB: review: accept / edit / reject per field
    DB-->>H: one decision per case (unique constraint) (audit: human.*, case.closed)
```

### State machines

```mermaid
stateDiagram-v2
    direction LR
    state "Analysis" as A {
        [*] --> pending
        pending --> running: worker claims
        running --> done: suggestion stored
        running --> pending: error, retry
        running --> failed: max attempts
        running --> pending: stale > 5 min (crashed worker)
        done --> pending: re-analysis requested
    }
    state "Case" as C {
        [*] --> nouveau
        nouveau --> nouveau: taken / released (lease)
        nouveau --> traite: decision
        nouveau --> manuel: out of scope
    }
```

## 5. Data model

```mermaid
erDiagram
    EMAILS ||--o{ SUGGESTIONS : "analysed into"
    EMAILS ||--o| REVIEWS : "closed by (unique)"
    EMAILS ||--o{ LLM_CALLS : "cost ledger"
    SUGGESTIONS ||--o| LLM_CALLS : "final call"
    EMAILS {
        int id
        text body_raw "purged after N days"
        text body_masked
        string arm "ai | control"
        string status "nouveau | traite | manuel"
        string analysis_status
        string assigned_to "lease holder"
        timestamptz queued_at
    }
    AUDIT_EVENTS {
        int seq "append-only, trigger-protected"
        string actor "human: | ai: | system:"
        string prev_hash
        string hash "sha256(prev + content)"
    }
    APP_CONFIG {
        string key "provider | model | prompt_version"
    }
    EVAL_RUNS {
        json summary "macro-F1, € / 1000, latency"
    }
```

## Where to look in the code

| Question | File |
|---|---|
| What can each role do? | `domain/roles.py` |
| How is priority decided? | `domain/priority_rules.py` |
| Deadlines and leases? | `domain/casework.py` |
| What is sent to the model? | `pii/masker.py`, `llm/prompts/v1.md`, `llm/gateway.py` |
| How does the worker avoid double work? | `application/analysis.py` (`claim_batch`) |
| How is a decision recorded? | `application/casework.py` (`submit_review`) |
| How is the gain measured? | `application/measurement.py` (`pilotage`) |
| How is tampering detected? | `audit/chain.py`, migration `0001` (trigger) |
| How does an external AI plug in? | `api/routers/ingest.py`, `application/sources.py`, `tools/vendor_sim.py` |
| How is a vendor scored without bias? | `application/sources.py` (`scoreboard`) |
| Storm mode? | `application/crisis.py`, `datagen/generate.py` (`generate_storm`) |
| Drift alarm? | `application/monitoring.py` |
| Oversight report? | `application/governance.py` (`oversight_report`) |

# Documentation

Read in this order. Each page fits on one or two screens.

| # | Page | Answers |
|---|---|---|
| 1 | [Actors and roles](actors-and-roles.md) | Who uses the tool, who can do what, what the AI never does |
| 2 | [Architecture](architecture.md) | Context → containers → components → flows → data model |
| 3 | [UX principles](ux.md) | Why each screen looks the way it does |
| 4 | [Quality attributes](quality-attributes.md) | Each quality, how it is met, and the test that proves it |
| 5 | [Security and privacy](security-privacy.md) | Threat model, data protection, production checklist |
| 6 | [Operations](operations.md) | Run, monitor, diagnose, ship a new prompt |
| 6b | [Deployment on AWS](deployment-aws.md) | CloudFront + EC2 Graviton + ECR + SSM, cost, commands |
| 7 | [Decisions](decisions/) | Why things are the way they are (ADRs) |

## Decisions

| ADR | Decision |
|---|---|
| [0001](decisions/0001-priority-by-rules-not-llm.md) | Priority comes from rules, not from the LLM |
| [0002](decisions/0002-provider-agnostic-gateway.md) | One provider-agnostic gateway with a rules fallback |
| [0003](decisions/0003-measure-with-a-control-arm.md) | Measure the gain with a control arm |
| [0004](decisions/0004-roles-and-token-auth.md) | Four roles, signed tokens, permissions per route |
| [0005](decisions/0005-asynchronous-analysis-worker.md) | Analysis runs asynchronously, outside the request |
| [0006](decisions/0006-case-lease-and-single-decision.md) | A case is leased to one handler; one decision per case |
| [0007](decisions/0007-runtime-ai-config-is-audited.md) | Runtime model changes are validated and audited |
| [0008](decisions/0008-vendor-neutral-control-tower.md) | Vendor-neutral control tower: champion, shadows, unbiased scoring |
| [0009](decisions/0009-storm-mode-drift-alarm-oversight-report.md) | Storm mode, drift alarm and sealed oversight report |

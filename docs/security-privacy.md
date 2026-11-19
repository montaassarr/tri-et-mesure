# Security and privacy

## Threat model (STRIDE, condensed)

| Threat | Example | Mitigation | Residual risk |
|---|---|---|---|
| **S**poofing | Someone acts as another handler | Signed JWT (HS256, 8 h), identity from the token only, never from the request body | Demo login has no password → OIDC in production |
| **T**ampering | Rewriting a past decision | Hash-chained audit log + DB trigger; verification endpoint | A DBA could drop the trigger *and* recompute the chain → ship hashes to WORM storage |
| **R**epudiation | "I never accepted that" | Every verdict is an audit event with the authenticated actor | — |
| **I**nformation disclosure | Personal data sent to a model vendor | Masking before every call; only masked prompts stored; register lists recipients | Postal addresses not masked |
| **I**nformation disclosure | Prompt injection in an e-mail ("ignore previous instructions…") | Prompt says the e-mail is data, never instructions; output constrained to a JSON schema; the model cannot act, only propose | A human always reviews |
| **D**enial of service | A flood of e-mails or a slow model | Async queue; worker concurrency limit; daily € budget with rules fallback | No HTTP rate limiting yet (reverse proxy) |
| **E**levation of privilege | A handler changes the model | Permission per route, separation of duties; 403 with a clear message | — |

## Data protection

| Topic | Choice |
|---|---|
| Purpose | Sort claim correspondence with human decision. Prototype, synthetic data. |
| Minimisation | Masking of names, phone numbers, e-mails, IBAN, NIR, plates and contract numbers before any model call |
| Retention | Original text erased after `RAW_RETENTION_DAYS` (default 30). Masked copy, decisions and audit log are kept. |
| Recipients | Model vendor receives masked text only. Listed live on the auditor's register. |
| Automated decisions | None. The AI proposes, a named human decides. |
| Access | Role-based, least privilege, see [actors and roles](actors-and-roles.md) |
| Secrets | `.env` only, never committed. Startup refuses the default secret when `ENVIRONMENT=prod`. |

## Production checklist

- [ ] OIDC with the company IdP (RS256 and JWKS) instead of demo login
- [ ] `AUTH_SECRET` and vendor keys in a secret manager (for example Azure Key Vault)
- [ ] TLS everywhere; `/api/ops/metrics` reachable from the internal network only
- [ ] Rate limiting at the reverse proxy
- [ ] Export audit hashes daily to immutable storage
- [ ] Data processing agreement with the model vendor (EU region, no training on data)

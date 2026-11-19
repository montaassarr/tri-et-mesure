# 0004 — Four roles, signed tokens, permissions per route

**Status:** accepted · 2026-11-18

## Context

The first version had one screen for everyone and a free-text "reviewer" field. That made
the audit actor forgeable and mixed duties: anyone could change the model and also decide
cases.

## Decision

- Four human roles (`domain/roles.py`), each with a fixed set of permissions. Every route
  declares the permission it needs (`require("cases.review")`).
- Identity comes from a signed JWT (HS256, 8 h, issuer checked). The audit actor is built
  from the token, never from the request body.
- Demo mode issues tokens from `POST /api/auth/demo-login`. Production replaces
  `decode_token` with OIDC validation against the company IdP (RS256 and JWKS). Guards,
  permissions and audit names stay unchanged.

## Consequences

- Separation of duties: configure ≠ decide ≠ audit.
- The UI builds its navigation from the permissions returned at login. Nothing is hidden
  in the front end that the API would still allow.
- Demo login has no password. That is acceptable for synthetic data only.

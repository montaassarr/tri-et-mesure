# 0001 — Priority is computed by rules, not by the LLM

**Status:** accepted · 2026-11-18

## Context

Priority decides which customer is called first. A handler must be able to understand and
challenge it. An LLM-generated priority can't be explained or reproduced.

## Decision

The LLM extracts **facts**: rehousing need, active leak, vulnerable person, deadline,
category. `domain/priority_rules.py` turns those facts into a priority with explicit
reasons. The rules are unit-tested and written test-first.

## Consequences

- Every priority shows its reasons in the UI and the audit log.
- Rules can change without changing or re-evaluating the prompt.
- The LLM's quality is measured on extraction, where errors are visible and correctable
  field by field.

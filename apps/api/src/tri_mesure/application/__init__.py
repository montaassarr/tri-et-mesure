"""Use cases. Orchestrates domain rules, adapters (LLM, database, audit) and transactions.

This layer knows nothing about HTTP: it raises `AppError` and the API turns it into a
Problem Details response. The rule is enforced by import-linter (see pyproject.toml).
"""

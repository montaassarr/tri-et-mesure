"""Logs and metrics (no HTTP here: the request middleware lives in api/middleware.py).

- Structured JSON logs (structlog) with a request id on every line.
- Prometheus metrics at /api/ops/metrics: HTTP traffic, model calls and cost, human
  decisions, analysis queue depth. These are the signals an on-call engineer and the AI
  team watch (see docs/operations.md).
"""

import logging

import structlog
from prometheus_client import Counter, Gauge, Histogram

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger()

HTTP_REQUESTS = Counter("tm_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "tm_http_request_duration_seconds",
    "HTTP request latency",
    ["route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
LLM_CALLS = Counter("tm_llm_calls_total", "Model calls", ["provider", "model", "outcome"])
LLM_COST_EUR = Counter("tm_llm_cost_eur_total", "Model spend in euros", ["model"])
LLM_LATENCY = Histogram(
    "tm_llm_call_duration_seconds",
    "Model call latency",
    ["provider"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32),
)
DECISIONS = Counter("tm_review_decisions_total", "Human decisions per item", ["verdict"])
CASES_CLOSED = Counter("tm_cases_closed_total", "Closed cases", ["arm", "status"])
ANALYSIS_QUEUE = Gauge("tm_analysis_queue_depth", "E-mails waiting for AI analysis")
AI_ACCEPTANCE = Gauge(
    "tm_ai_acceptance_rate",
    "Share of the champion's last decisions accepted without correction",
    ["source"],
)

"""HTTP middleware: request id, one structured log line per request, HTTP metrics."""

import contextlib
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.requests import Request
from starlette.responses import Response

from tri_mesure.observability import HTTP_LATENCY, HTTP_REQUESTS, log

REQUEST_ID_HEADER = "X-Request-ID"


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a request id, log one line per request and record HTTP metrics."""
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, route_path, str(status)).inc()
        HTTP_LATENCY.labels(route_path).observe(elapsed)
        # Probes and metric scrapes are high-frequency noise: count them, don't log them.
        quiet = any(part in route_path for part in ("/health", "/ops/metrics"))
        if not quiet:
            # Logging is best-effort: a broken log stream (closed terminal, full disk) must
            # never turn a successful request into a 500.
            with contextlib.suppress(Exception):
                log.info(
                    "http_request",
                    method=request.method,
                    route=route_path,
                    status=status,
                    duration_ms=round(elapsed * 1000, 1),
                )
        structlog.contextvars.unbind_contextvars("request_id")

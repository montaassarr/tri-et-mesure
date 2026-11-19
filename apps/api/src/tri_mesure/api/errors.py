"""Uniform error responses: RFC 9457 "Problem Details" (application/problem+json).

Every error the API returns has the same shape, a human-readable French `detail` the UI can
show as-is, and the request id so a support engineer can find the matching log line.
"""

import contextlib
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from tri_mesure.application.errors import AppError
from tri_mesure.observability import log

_TITLES = {
    400: "Requête invalide",
    401: "Non authentifié",
    403: "Accès refusé",
    404: "Introuvable",
    409: "Conflit",
    422: "Données invalides",
    429: "Trop de requêtes",
    500: "Erreur interne",
}


def problem(
    request: Request, status: int, detail: str, extra: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": _TITLES.get(status, "Erreur"),
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem(request, exc.status, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        response = problem(request, exc.status_code, str(exc.detail))
        for key, value in (exc.headers or {}).items():
            response.headers[key] = value
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        detail = "; ".join(f"{e['field'] or 'requête'} : {e['message']}" for e in errors)
        return problem(request, 422, detail, {"errors": errors})

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        with contextlib.suppress(Exception):  # logging is best-effort
            log.warning("integrity_conflict", error=str(exc.orig)[:200])
        return problem(request, 409, "Conflit : cette action a déjà été enregistrée.")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        with contextlib.suppress(Exception):  # logging is best-effort
            log.exception("unhandled_error", path=request.url.path)
        return problem(request, 500, "Une erreur inattendue est survenue.")

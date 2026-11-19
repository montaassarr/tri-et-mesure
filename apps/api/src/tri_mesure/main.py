"""FastAPI application: wiring only (middleware, error handlers, routers, lifecycle)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tri_mesure import __version__
from tri_mesure.api import errors
from tri_mesure.api.middleware import REQUEST_ID_HEADER, request_context_middleware
from tri_mesure.api.routers import ai, audit, auth, cases, ingest, pilotage, system, workspace
from tri_mesure.application import governance, measurement, sources
from tri_mesure.application.analysis import AnalysisWorker
from tri_mesure.db.session import get_sessionmaker
from tri_mesure.observability import log
from tri_mesure.settings import DEV_AUTH_SECRET, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.auth_secret == DEV_AUTH_SECRET:
        if settings.environment == "prod":
            raise RuntimeError("AUTH_SECRET must be set in production")
        log.warning("dev_auth_secret_in_use")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        await measurement.ensure_assumptions(session)
        await sources.ensure_internal_source(session)
        purged = await governance.purge_raw_bodies(session, settings.raw_retention_days)

    worker = AnalysisWorker(settings, sessionmaker)
    app.state.worker = worker
    if settings.worker_enabled:
        worker.start()
    log.info(
        "startup",
        version=__version__,
        provider=settings.llm_provider,
        worker=settings.worker_enabled,
        purged=purged,
    )
    try:
        yield
    finally:
        await worker.stop()
        log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Tri & Mesure API",
        version=__version__,
        description=(
            "Tri du courrier sinistres : l'IA propose, un humain authentifié décide, l'outil "
            "mesure. Prototype étudiant, données synthétiques."
        ),
        lifespan=lifespan,
    )
    app.middleware("http")(request_context_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.web_origin.split(",")],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    errors.install(app)
    for module in (system, auth, cases, workspace, pilotage, audit, ai, ingest):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()

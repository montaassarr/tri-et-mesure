"""Machine-to-machine API for external AI vendors (the "plug any AI" contract).

A vendor needs only an API key and two calls:
  1. GET  /api/ingest/cases                     -> open cases, masked text only
  2. POST /api/ingest/cases/{id}/suggestion     -> its proposal, same schema as ours
It never sees identities, other vendors' answers, or human decisions.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from tri_mesure.api.deps import SessionDep
from tri_mesure.api.schemas import ExternalSuggestionIn, ExternalSuggestionOut, IngestCase
from tri_mesure.application import sources
from tri_mesure.db.models import AISource

router = APIRouter(prefix="/ingest", tags=["ingest (vendors)"])


async def current_source(
    session: SessionDep, x_api_key: Annotated[str | None, Header()] = None
) -> AISource:
    source = await sources.authenticate(session, x_api_key or "")
    if source is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Clé d'API absente, invalide ou désactivée"
        )
    return source


SourceDep = Annotated[AISource, Depends(current_source)]


@router.get(
    "/cases",
    response_model=list[IngestCase],
    summary="Open cases this vendor has not proposed on yet (masked)",
)
async def pending(
    session: SessionDep, source: SourceDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[IngestCase]:
    return [
        IngestCase(id=e.id, received_at=e.received_at, subject=e.subject_masked, body=e.body_masked)
        for e in await sources.pending_for(session, source, limit)
    ]


@router.post(
    "/cases/{case_id}/suggestion",
    response_model=ExternalSuggestionOut,
    summary="Submit a proposal (champion: shown to handlers; otherwise shadow)",
)
async def submit(
    case_id: int, data: ExternalSuggestionIn, session: SessionDep, source: SourceDep
) -> ExternalSuggestionOut:
    suggestion = await sources.submit_external(
        session, source, case_id, data, data.model, data.cost_eur, data.latency_ms
    )
    champion = await sources.get_champion(session)
    return ExternalSuggestionOut(
        suggestion_id=suggestion.id, mode="champion" if champion == source.code else "shadow"
    )

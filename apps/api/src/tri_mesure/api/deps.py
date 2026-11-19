"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tri_mesure.api.security import Principal, current_principal, require
from tri_mesure.application.casework import Actor
from tri_mesure.db.session import get_session
from tri_mesure.settings import Settings, get_settings

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
UserDep = Annotated[Principal, Depends(current_principal)]

CanReadCases = Annotated[Principal, Depends(require("cases.read"))]
CanReview = Annotated[Principal, Depends(require("cases.review"))]
CanPilot = Annotated[Principal, Depends(require("pilotage.read"))]
CanEditAssumptions = Annotated[Principal, Depends(require("assumptions.write"))]
CanAudit = Annotated[Principal, Depends(require("audit.read"))]
CanReadEval = Annotated[Principal, Depends(require("eval.read"))]
CanRunEval = Annotated[Principal, Depends(require("eval.run"))]
CanConfigure = Annotated[Principal, Depends(require("config.write"))]
CanSeed = Annotated[Principal, Depends(require("demo.seed"))]
CanManageCrisis = Annotated[Principal, Depends(require("crisis.manage"))]


def actor_of(principal: Principal) -> Actor:
    return Actor(name=principal.name, role=principal.role)

"""Authentication and authorisation.

Demo mode: `POST /api/auth/demo-login` issues a short-lived signed JWT for a chosen role.
Production path (documented in ADR 0004): the token comes from the company identity
provider via OIDC; only `decode_token` changes (RS256 + the provider's JWKS). Every guard,
permission and audit actor stays the same.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tri_mesure.domain.roles import ROLES, has_permission
from tri_mesure.settings import Settings, get_settings

_ALGORITHM = "HS256"
_ISSUER = "tri-et-mesure"
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    name: str
    role: str

    @property
    def actor(self) -> str:
        """How this person appears in the audit log."""
        return f"human:{self.name} ({self.role})"

    @property
    def permissions(self) -> list[str]:
        return sorted(ROLES[self.role].permissions)


def issue_token(principal: Principal, settings: Settings) -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(minutes=settings.token_ttl_minutes)
    token = jwt.encode(
        {
            "sub": principal.name,
            "role": principal.role,
            "iss": _ISSUER,
            "iat": datetime.now(UTC),
            "exp": expires,
        },
        settings.auth_secret,
        algorithm=_ALGORITHM,
    )
    return token, expires


def decode_token(token: str, settings: Settings) -> Principal:
    try:
        claims = jwt.decode(
            token,
            settings.auth_secret,
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            options={"require": ["sub", "role", "exp"]},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Session invalide ou expirée",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    role = str(claims["role"])
    if role not in ROLES:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Rôle inconnu")
    return Principal(name=str(claims["sub"]), role=role)


async def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials, settings)


def require(permission: str) -> Callable[..., Awaitable[Principal]]:
    """Route dependency: the caller must hold `permission`."""

    async def guard(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if not has_permission(principal.role, permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Action non autorisée pour le rôle « {ROLES[principal.role].label} »",
            )
        return principal

    return guard

"""Demo authentication: choose a role, receive a signed token."""

from fastapi import APIRouter

from tri_mesure.api.deps import SettingsDep, UserDep
from tri_mesure.api.schemas import LoginIn, RoleOut, TokenOut, UserOut
from tri_mesure.api.security import Principal, issue_token
from tri_mesure.domain.roles import ROLES

router = APIRouter(prefix="/auth", tags=["auth"])


def _user(p: Principal) -> UserOut:
    info = ROLES[p.role]
    return UserOut(
        name=p.name, role=p.role, role_label=info.label, permissions=p.permissions, home=info.home
    )


@router.get("/roles", response_model=list[RoleOut], summary="The four human roles")
async def roles() -> list[RoleOut]:
    return [
        RoleOut(
            code=code,
            label=r.label,
            mission=r.mission,
            permissions=sorted(r.permissions),
            home=r.home,
        )
        for code, r in ROLES.items()
    ]


@router.post(
    "/demo-login",
    response_model=TokenOut,
    summary="Demo only: sign in as any role (production uses the company IdP)",
)
async def demo_login(data: LoginIn, settings: SettingsDep) -> TokenOut:
    principal = Principal(name=data.name.strip(), role=data.role)
    token, expires = issue_token(principal, settings)
    return TokenOut(access_token=token, expires_at=expires, user=_user(principal))


@router.get("/me", response_model=UserOut)
async def me(principal: UserDep) -> UserOut:
    return _user(principal)

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.organizations import OrganizationRole
from app.utils.auth.shared import get_current_session

# Each role holds every power of the roles ranked below it: a MEMBER reads and
# deploys, an ADMIN also creates and changes projects and applications, and an
# OWNER also deletes them and their deployments.
ROLE_RANKS = {
    OrganizationRole.MEMBER: 0,
    OrganizationRole.ADMIN: 1,
    OrganizationRole.OWNER: 2,
}


# Only members get this far, and they can already read the resource, so a 403
# confirms nothing a 404 would hide.
def ensure_role(role: OrganizationRole, required_role: OrganizationRole) -> None:
    if ROLE_RANKS[role] < ROLE_RANKS[required_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This action requires the '{required_role.value}' role!",
        )


def require_role[M](
    resolve: Callable[[AsyncSession, int, uuid.UUID, OrganizationRole], Awaitable[M]],
    required_role: OrganizationRole,
) -> Callable[..., Awaitable[M]]:
    """A dependency resolving the `id` path parameter with `resolve`, one of the
    `get_member_*` helpers, for a caller who holds at least `required_role` in
    the resource's organization."""

    async def dependency(
        id: uuid.UUID,
        auth_session: dict = Depends(get_current_session),
        db_session: AsyncSession = Depends(get_db_session),
    ) -> M:
        return await resolve(db_session, auth_session["user_id"], id, required_role)

    return dependency

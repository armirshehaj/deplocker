from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError

from app.core import redis
from app.core.conf import settings
from app.models import OrganizationMembersModel, OrganizationModel, UserModel
from app.schemas.auth import SessionData
from app.schemas.organizations import OrganizationRole
from app.utils.auth.deplocker_auth import get_password_hash
from app.utils.text.slug_generator import generate_slug

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


async def _add_default_organization(db_session: AsyncSession, user: UserModel) -> None:
    name = f"{user.username}'s organization"
    organization = OrganizationModel(
        owner_id=user.id,
        name=name,
        slug=await _unique_organization_slug(db_session, generate_slug(name)),
    )
    db_session.add(organization)
    await db_session.flush()

    db_session.add(
        OrganizationMembersModel(
            user_id=user.id,
            organization_id=organization.id,
            role=OrganizationRole.OWNER,
        )
    )


async def _login_response[R: (JSONResponse, RedirectResponse)](
    db_user: UserModel, response: R
) -> R:
    """Opens a session for the user and sets its cookie on `response`: JSON for
    password and passkey logins, a redirect to the frontend for OAuth2."""
    session_data = SessionData(
        user_id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
        created_at=db_user.created_at,
    )

    session_id = str(uuid.uuid4())
    await redis.client.setex(
        f"session:{session_id}", timedelta(days=1), session_data.model_dump_json()
    )

    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        secure=settings.ENVIRONMENT != "dev",
        samesite="strict",
        expires=int(timedelta(days=1).total_seconds()),
    )
    return response


async def get_current_session(request: Request) -> dict[str, Any]:
    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="There is no active session!",
        )

    session_data = await redis.client.get(f"session:{session_id}")
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired, or is invalid!",
        )

    return SessionData.model_validate_json(session_data).model_dump(mode="json")


def oauth_failure_redirect(reason: str) -> RedirectResponse:
    """OAuth callbacks are browser navigations, so failures go back to the login
    page as a query parameter rather than rendering an API error body."""
    # `reason` can carry a provider-supplied error, so keep it to an opaque slug.
    code = re.sub(r"[^a-z_]", "", reason.lower())[:40] or "unknown_error"
    return RedirectResponse(f"{settings.FRONTEND_URL}/login?error={code}")


async def _unique_username(db_session: AsyncSession, base: str) -> str:
    root = re.sub(r"[^a-zA-Z0-9_.-]", "", base).strip(".-_") or "user"
    candidate = root
    suffix = 1
    while await db_session.scalar(
        select(exists().where(UserModel.username == candidate))
    ):
        suffix += 1
        candidate = f"{root}-{suffix}"
    return candidate


# Usernames are unique, but their slugs need not be ("a_b" and "a-b" both give
# "a-bs-organization"), and registration shouldn't fail over the default
# organization's handle.
async def _unique_organization_slug(db_session: AsyncSession, root: str) -> str:
    candidate = root
    suffix = 1
    while await db_session.scalar(
        select(exists().where(OrganizationModel.slug == candidate))
    ):
        suffix += 1
        candidate = f"{root}-{suffix}"
    return candidate


async def get_or_create_oauth_user(
    db_session: AsyncSession,
    *,
    email: str,
    full_name: str | None,
    username_hint: str,
) -> UserModel:
    """Resolve the provider's account to a local user, creating one if needed.

    The database, not the lookup, enforces uniqueness: when a concurrent callback
    creates the same user first, the insert raises `IntegrityError` and that
    user is returned instead. A clash on the username or the default
    organization's slug raises the same error but leaves no user to return, so
    it ends in a 409 a retry would avoid; the logged constraint name tells these
    cases apart.
    """
    db_user: UserModel | None = await db_session.scalar(
        select(UserModel).where(UserModel.email == email)
    )
    if db_user:
        if not db_user.is_active:
            # The provider verified the address, which confirms the account
            db_user.is_active = True
            await db_session.commit()
        return db_user

    username = await _unique_username(db_session, username_hint)
    new_user = UserModel(
        username=username,
        email=email,
        full_name=full_name or username,
        password=get_password_hash(uuid.uuid4().hex),
        is_active=True,  # The provider already verified the address
    )

    try:
        db_session.add(new_user)
        await db_session.flush()
        await _add_default_organization(db_session, new_user)
        await db_session.commit()
    except IntegrityError:
        await db_session.rollback()
        db_user = await db_session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        if db_user is None:
            logger.exception("Could not provision an account for %s", email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not create an account for this email address.",
            ) from None
        return db_user

    await db_session.refresh(new_user)
    return new_user


async def oauth_login_redirect(db_user: UserModel) -> RedirectResponse:
    return await _login_response(db_user, RedirectResponse(settings.FRONTEND_URL))

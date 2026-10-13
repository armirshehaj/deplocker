from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.core.conf import settings
from app.core.database import get_db_session
from app.routers.auth import router
from app.utils.auth.google_oauth import (
    fetch_google_access_token,
    fetch_google_user_info,
)
from app.utils.auth.shared import (
    get_or_create_oauth_user,
    oauth_failure_redirect,
    oauth_login_redirect,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)

google_oauth_router = APIRouter(prefix="/google", tags=["Google OAuth"])


@google_oauth_router.get("/login")
async def google_oauth2_login() -> RedirectResponse:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(f"{settings.GOOGLE_AUTH_URL}?{urlencode(params)}")


@google_oauth_router.get("/callback")
async def google_oauth2_callback(
    code: str | None = None,
    error: str | None = None,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    if error or not code:
        logger.info("Google callback without a usable code: %s", error or "no code")
        return oauth_failure_redirect(error or "missing_code")

    try:
        token_response = await fetch_google_access_token(code)
        access_token = token_response.get("access_token")

        if not access_token:
            logger.warning("Google token exchange returned no access token")
            return oauth_failure_redirect("google_token_exchange_failed")

        user_info = await fetch_google_user_info(access_token)
    except HTTPException:
        return oauth_failure_redirect("google_unavailable")

    email = user_info.get("email")
    if not email:
        return oauth_failure_redirect("google_email_missing")

    # An unverified address would let anyone claim an existing account by signing
    # up to the provider with its email.
    if not user_info.get("email_verified", False):
        logger.warning("Rejected an unverified Google address")
        return oauth_failure_redirect("google_email_unverified")

    db_user = await get_or_create_oauth_user(
        db_session,
        email=email,
        full_name=user_info.get("name"),
        username_hint=email.split("@")[0],
    )

    return await oauth_login_redirect(db_user)


router.include_router(google_oauth_router, tags=["Google OAuth"])

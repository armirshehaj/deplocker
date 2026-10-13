from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.core.conf import settings
from app.core.database import get_db_session
from app.utils.auth.github_oauth import (
    fetch_github_access_token,
    fetch_github_user_email,
    fetch_github_user_info,
)
from app.utils.auth.shared import (
    get_or_create_oauth_user,
    oauth_failure_redirect,
    oauth_login_redirect,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from . import router

logger = logging.getLogger(__name__)

github_oauth_router = APIRouter(prefix="/github", tags=["GitHub OAuth"])


@github_oauth_router.get("/login")
async def github_oauth2_login() -> RedirectResponse:
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
    }
    return RedirectResponse(f"{settings.GITHUB_AUTH_URL}?{urlencode(params)}")


@github_oauth_router.get("/callback")
async def github_oauth2_callback(
    code: str | None = None,
    error: str | None = None,
    db_session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    if error or not code:
        logger.info("GitHub callback without a usable code: %s", error or "no code")
        return oauth_failure_redirect(error or "missing_code")

    try:
        token_response = await fetch_github_access_token(code)
        access_token = token_response.get("access_token")

        if not access_token:
            logger.warning("GitHub token exchange returned no access token")
            return oauth_failure_redirect("github_token_exchange_failed")

        user_info = await fetch_github_user_info(access_token)
        email = await fetch_github_user_email(access_token)
    except HTTPException:
        return oauth_failure_redirect("github_unavailable")

    db_user = await get_or_create_oauth_user(
        db_session,
        email=email,
        full_name=user_info.get("name"),
        username_hint=user_info.get("login") or email.split("@")[0],
    )

    return await oauth_login_redirect(db_user)


router.include_router(github_oauth_router, tags=["GitHub OAuth"])

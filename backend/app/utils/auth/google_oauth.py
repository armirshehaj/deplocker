import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.conf import settings

logger = logging.getLogger(__name__)


async def _google_request(
    client: httpx.AsyncClient, method: str, url: str, **kw: Any
) -> dict[str, Any]:
    try:
        resp = await client.request(method, url, **kw)
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
        return payload
    except httpx.HTTPStatusError as exc:
        # Reachable, but rejected: bad code, redirect mismatch
        logger.warning(
            "Google API %s %s -> %s: %s",
            method,
            url,
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google rejected the authentication request.",
        ) from exc
    except (httpx.RequestError, ValueError) as exc:  # network error or bad JSON
        logger.error("Google API %s %s failed: %r", method, url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google. Please try again.",
        ) from exc


async def fetch_google_access_token(code: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        return await _google_request(
            client,
            "POST",
            settings.GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )


async def fetch_google_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        return await _google_request(
            client,
            "GET",
            settings.GOOGLE_USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

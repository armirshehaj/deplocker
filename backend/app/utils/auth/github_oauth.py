import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.conf import settings

logger = logging.getLogger(__name__)


def _api_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _github_request(method: str, url: str, **kw: Any) -> Any:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.request(method, url, **kw)
            resp.raise_for_status()
            payload: Any = resp.json()
        except httpx.HTTPStatusError as exc:
            # Reachable, but rejected: revoked token, missing scope, rate limit
            logger.warning(
                "GitHub API %s %s -> %s: %s",
                method,
                url,
                exc.response.status_code,
                exc.response.text,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub rejected the authentication request.",
            ) from exc
        except (httpx.RequestError, ValueError) as exc:  # network error or bad JSON
            logger.error("GitHub API %s %s failed: %r", method, url, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not reach GitHub. Please try again.",
            ) from exc

    # The token endpoint answers OAuth failures with HTTP 200 and an error body,
    # so raise_for_status() never sees them.
    if isinstance(payload, dict) and payload.get("error"):
        logger.warning(
            "GitHub API %s %s -> %s: %s",
            method,
            url,
            payload.get("error"),
            payload.get("error_description"),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub rejected the authentication request.",
        )

    return payload


def _expect_dict(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        logger.error("GitHub returned an unexpected payload: %r", payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub returned an unexpected response.",
        )
    return payload


async def fetch_github_access_token(code: str) -> dict[str, Any]:
    payload = await _github_request(
        "POST",
        settings.GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "code": code,
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    return _expect_dict(payload)


async def fetch_github_user_info(access_token: str) -> dict[str, Any]:
    payload = await _github_request(
        "GET", settings.GITHUB_USER_INFO_URL, headers=_api_headers(access_token)
    )
    return _expect_dict(payload)


async def fetch_github_user_email(access_token: str) -> str:
    """Resolve the account's primary verified address.

    `/user` only exposes an email when the account publishes one, which is off by
    default, so the address always comes from the `user:email` scope instead.
    """
    payload = await _github_request(
        "GET", settings.GITHUB_USER_EMAILS_URL, headers=_api_headers(access_token)
    )

    if not isinstance(payload, list):
        logger.error("GitHub returned an unexpected email payload: %r", payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not read the email addresses on the GitHub account.",
        )

    fallback: str | None = None
    for entry in payload:
        if not isinstance(entry, dict) or not entry.get("verified"):
            continue
        email = entry.get("email")
        if not isinstance(email, str):
            continue
        if entry.get("primary"):
            return email
        fallback = fallback or email

    if fallback:
        return fallback

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No verified email address on the GitHub account.",
    )

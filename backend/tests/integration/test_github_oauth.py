from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.models import UserModel
from app.schemas.auth import UserRole

GITHUB_USER = {"login": "octocat", "id": 4711, "name": "Octo Cat", "email": None}
GITHUB_EMAIL = "octocat@example.com"


def _error_code(location: str) -> str:
    return parse_qs(urlparse(location).query)["error"][0]


_DEFAULT_TOKEN = {"access_token": "gho_valid"}


def _patch_github(
    user_info: dict | None = None,
    email: str = GITHUB_EMAIL,
    token: dict = _DEFAULT_TOKEN,
) -> tuple:
    return (
        patch(
            "app.routers.auth.github_oauth.fetch_github_access_token",
            new=AsyncMock(return_value=token),
        ),
        patch(
            "app.routers.auth.github_oauth.fetch_github_user_info",
            new=AsyncMock(return_value=user_info or GITHUB_USER),
        ),
        patch(
            "app.routers.auth.github_oauth.fetch_github_user_email",
            new=AsyncMock(return_value=email),
        ),
    )


@pytest.mark.anyio
async def test_github_login_redirects_to_github(client: AsyncClient) -> None:
    response = await client.get("/auth/github/login", follow_redirects=False)

    assert response.status_code == 307

    location = response.headers["location"]
    assert location.startswith(settings.GITHUB_AUTH_URL)

    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == [settings.GITHUB_CLIENT_ID]
    assert query["redirect_uri"] == [settings.GITHUB_REDIRECT_URI]
    assert query["scope"] == ["read:user user:email"]


@pytest.mark.anyio
async def test_github_callback_creates_user_with_private_email(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    """`/user` exposes no email for a private account, so the address comes from
    the `user:email` scope instead."""

    token_patch, info_patch, email_patch = _patch_github()

    with token_patch, info_patch, email_patch:
        response = await client.get(
            "/auth/github/callback",
            params={"code": "valid-auth-code"},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == settings.FRONTEND_URL
    assert "session_id" in response.cookies

    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == GITHUB_EMAIL)
    )
    assert db_user is not None
    assert db_user.username == "octocat"
    assert db_user.full_name == "Octo Cat"
    assert db_user.role == UserRole.USER
    assert db_user.is_active is True


@pytest.mark.anyio
async def test_github_callback_without_a_profile_name(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    """`name` is null for accounts that never filled in a display name, and the
    column is NOT NULL."""

    token_patch, info_patch, email_patch = _patch_github(
        user_info={"login": "nameless", "id": 99, "name": None, "email": None},
        email="nameless@example.com",
    )

    with token_patch, info_patch, email_patch:
        response = await client.get(
            "/auth/github/callback",
            params={"code": "valid-auth-code"},
            follow_redirects=False,
        )

    assert response.status_code == 307

    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == "nameless@example.com")
    )
    assert db_user is not None
    assert db_user.full_name == "nameless"


@pytest.mark.anyio
async def test_github_callback_username_collision(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    """Two providers can hand us the same username for different accounts."""

    first = _patch_github(email="first@example.com")
    with first[0], first[1], first[2]:
        await client.get(
            "/auth/github/callback",
            params={"code": "code-one"},
            follow_redirects=False,
        )

    second = _patch_github(email="second@example.com")
    with second[0], second[1], second[2]:
        response = await client.get(
            "/auth/github/callback",
            params={"code": "code-two"},
            follow_redirects=False,
        )

    assert response.status_code == 307

    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == "second@example.com")
    )
    assert db_user is not None
    assert db_user.username == "octocat-2"


@pytest.mark.anyio
async def test_github_callback_missing_access_token(client: AsyncClient) -> None:
    token_patch, info_patch, email_patch = _patch_github(token={})

    with token_patch, info_patch, email_patch:
        response = await client.get(
            "/auth/github/callback",
            params={"code": "bad-auth-code"},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert _error_code(response.headers["location"]) == "github_token_exchange_failed"


@pytest.mark.anyio
async def test_github_callback_provider_failure(client: AsyncClient) -> None:
    """A rejected or unreachable GitHub returns the browser to the login page."""

    from fastapi import HTTPException

    with (
        patch(
            "app.routers.auth.github_oauth.fetch_github_access_token",
            new=AsyncMock(side_effect=HTTPException(status_code=502, detail="down")),
        ),
    ):
        response = await client.get(
            "/auth/github/callback",
            params={"code": "valid-auth-code"},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert _error_code(response.headers["location"]) == "github_unavailable"


@pytest.mark.anyio
async def test_github_callback_consent_declined(client: AsyncClient) -> None:
    response = await client.get(
        "/auth/github/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert _error_code(response.headers["location"]) == "access_denied"

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.conf import settings
from app.utils.auth.github_oauth import (
    fetch_github_access_token,
    fetch_github_user_email,
)


def _response(
    status_code: int = 200,
    *,
    json: Any = None,
    text: str | None = None,
    url: str = "https://api.github.com/user",
) -> httpx.Response:
    request = httpx.Request("GET", url)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json, request=request)


def _patch_request(response: httpx.Response | Exception) -> Any:
    kwargs = (
        {"side_effect": response}
        if isinstance(response, Exception)
        else {"return_value": response}
    )
    return patch.object(httpx.AsyncClient, "request", new=AsyncMock(**kwargs))


@pytest.mark.anyio
async def test_token_exchange_sends_client_credentials() -> None:
    """The token request must carry the app credentials and ask for JSON, since
    GitHub answers form-encoded by default."""

    mock_request = AsyncMock(return_value=_response(json={"access_token": "gho_x"}))

    with patch.object(httpx.AsyncClient, "request", new=mock_request):
        token = await fetch_github_access_token("valid-code")

    assert token["access_token"] == "gho_x"

    _, kwargs = mock_request.call_args
    assert kwargs["headers"]["Accept"] == "application/json"
    assert kwargs["data"]["client_id"] == settings.GITHUB_CLIENT_ID
    assert kwargs["data"]["client_secret"] == settings.GITHUB_CLIENT_SECRET
    assert kwargs["data"]["redirect_uri"] == settings.GITHUB_REDIRECT_URI
    assert kwargs["data"]["code"] == "valid-code"


@pytest.mark.anyio
async def test_token_exchange_error_returned_with_http_200() -> None:
    """GitHub reports a bad or replayed code with a 200 and an error body."""

    body = {
        "error": "bad_verification_code",
        "error_description": "The code passed is incorrect or expired.",
    }

    with _patch_request(_response(json=body)), pytest.raises(HTTPException) as exc_info:
        await fetch_github_access_token("expired-code")

    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_form_encoded_response_is_not_a_server_error() -> None:
    with (
        _patch_request(_response(text="access_token=gho_x&scope=&token_type=bearer")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await fetch_github_access_token("valid-code")

    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_network_failure_reports_bad_gateway() -> None:
    with (
        _patch_request(httpx.ConnectTimeout("timed out")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await fetch_github_access_token("valid-code")

    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_email_prefers_primary_verified_address() -> None:
    emails = [
        {"email": "secondary@example.com", "primary": False, "verified": True},
        {"email": "primary@example.com", "primary": True, "verified": True},
    ]

    with _patch_request(_response(json=emails)):
        assert await fetch_github_user_email("gho_x") == "primary@example.com"


@pytest.mark.anyio
async def test_email_skips_unverified_primary() -> None:
    """An unverified address would let anyone claim an account by its email."""

    emails = [
        {"email": "unverified@example.com", "primary": True, "verified": False},
        {"email": "verified@example.com", "primary": False, "verified": True},
    ]

    with _patch_request(_response(json=emails)):
        assert await fetch_github_user_email("gho_x") == "verified@example.com"


@pytest.mark.anyio
async def test_email_accepts_private_noreply_address() -> None:
    emails = [
        {
            "email": "4711+octocat@users.noreply.github.com",
            "primary": True,
            "verified": True,
            "visibility": None,
        },
    ]

    with _patch_request(_response(json=emails)):
        email = await fetch_github_user_email("gho_x")

    assert email == "4711+octocat@users.noreply.github.com"


@pytest.mark.anyio
async def test_email_without_any_verified_address_fails() -> None:
    emails = [{"email": "unverified@example.com", "primary": True, "verified": False}]

    with (
        _patch_request(_response(json=emails)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await fetch_github_user_email("gho_x")

    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_email_scope_not_granted() -> None:
    with (
        _patch_request(_response(403, json={"message": "Requires authentication"})),
        pytest.raises(HTTPException) as exc_info,
    ):
        await fetch_github_user_email("gho_x")

    assert exc_info.value.status_code == 400

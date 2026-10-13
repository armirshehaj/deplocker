from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.models import PasskeyModel, UserModel
from app.utils.auth.passkeys import CHALLENGE_COOKIE
from tests.soft_authenticator import SoftAuthenticator

EnrolPasskey = Callable[..., Awaitable[dict[str, Any]]]


@pytest.fixture()
def authenticator() -> SoftAuthenticator:
    return SoftAuthenticator(settings.RP_ID, settings.FRONTEND_URL)


@pytest.fixture()
async def enrol_passkey(
    authenticated_client: AsyncClient, authenticator: SoftAuthenticator
) -> EnrolPasskey:
    """Runs both legs of the enrolment ceremony and returns the stored passkey."""

    async def enrol(name: str = "MacBook Touch ID") -> dict[str, Any]:
        options = await authenticated_client.post("/auth/passkeys/register/options")
        assert options.status_code == 200

        response = await authenticated_client.post(
            "/auth/passkeys/register",
            json={"name": name, "credential": authenticator.create(options.json())},
        )
        assert response.status_code == 201

        passkey: dict[str, Any] = response.json()
        return passkey

    return enrol


@pytest.mark.anyio
async def test_registration_options_require_a_session(client: AsyncClient) -> None:
    response = await client.post("/auth/passkeys/register/options")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_registration_options_scope_the_credential_to_the_frontend_host(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post("/auth/passkeys/register/options")

    assert response.status_code == 200

    options = response.json()
    assert options["rp"]["id"] == settings.RP_ID
    assert options["rp"]["name"] == settings.WEBAUTHN_RP_NAME
    assert options["user"]["name"] == "test_user"
    # Discoverable, so the login page can offer the account without a username.
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["challenge"]


@pytest.mark.anyio
async def test_registration_stores_the_credential(
    enrol_passkey: EnrolPasskey,
    authenticator: SoftAuthenticator,
    test_db_session: AsyncSession,
) -> None:
    passkey = await enrol_passkey()

    assert passkey["name"] == "MacBook Touch ID"
    assert passkey["last_used_at"] is None

    stored = await test_db_session.scalar(
        select(PasskeyModel).where(
            PasskeyModel.credential_id == authenticator.credential_id
        )
    )

    assert stored is not None
    assert stored.public_key
    assert stored.sign_count == 0
    assert stored.transports == ["internal", "hybrid"]


@pytest.mark.anyio
async def test_registration_rejects_a_credential_without_a_challenge(
    authenticated_client: AsyncClient, authenticator: SoftAuthenticator
) -> None:
    response = await authenticated_client.post(
        "/auth/passkeys/register",
        json={
            "name": "Forged",
            "credential": authenticator.create({"challenge": "not-a-challenge"}),
        },
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_a_registration_challenge_is_single_use(
    authenticated_client: AsyncClient, authenticator: SoftAuthenticator
) -> None:
    options = await authenticated_client.post("/auth/passkeys/register/options")
    credential = authenticator.create(options.json())
    payload = {"name": "Replayed", "credential": credential}

    assert (
        await authenticated_client.post("/auth/passkeys/register", json=payload)
    ).status_code == 201

    replay = await authenticated_client.post("/auth/passkeys/register", json=payload)

    assert replay.status_code == 400


@pytest.mark.anyio
async def test_enrolled_passkeys_are_excluded_from_a_new_ceremony(
    authenticated_client: AsyncClient,
    authenticator: SoftAuthenticator,
    enrol_passkey: EnrolPasskey,
) -> None:
    await enrol_passkey()

    response = await authenticated_client.post("/auth/passkeys/register/options")

    excluded = [entry["id"] for entry in response.json()["excludeCredentials"]]
    assert len(excluded) == 1


@pytest.mark.anyio
async def test_listing_returns_the_enrolled_passkeys(
    authenticated_client: AsyncClient, enrol_passkey: EnrolPasskey
) -> None:
    passkey = await enrol_passkey()

    response = await authenticated_client.get("/auth/passkeys")

    assert response.status_code == 200
    assert [entry["id"] for entry in response.json()] == [passkey["id"]]


@pytest.mark.anyio
async def test_deleting_a_passkey_removes_it(
    authenticated_client: AsyncClient, enrol_passkey: EnrolPasskey
) -> None:
    passkey = await enrol_passkey()

    response = await authenticated_client.delete(f"/auth/passkeys/{passkey['id']}")

    assert response.status_code == 204
    assert (await authenticated_client.get("/auth/passkeys")).json() == []


@pytest.mark.anyio
async def test_deleting_an_unknown_passkey_is_not_found(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.delete(
        "/auth/passkeys/8d4e1a2b-0c33-4f6a-9d21-6b0f5c7e4a19"
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_login_options_hand_out_a_challenge_cookie(client: AsyncClient) -> None:
    response = await client.post("/auth/passkeys/login/options")

    assert response.status_code == 200
    assert response.json()["rpId"] == settings.RP_ID
    # Usernameless: the browser picks from the discoverable credentials it holds.
    assert not response.json().get("allowCredentials")
    assert CHALLENGE_COOKIE in response.cookies


@pytest.mark.anyio
async def test_login_without_a_challenge_cookie_is_rejected(
    client: AsyncClient, authenticator: SoftAuthenticator
) -> None:
    response = await client.post(
        "/auth/passkeys/login",
        json={"credential": authenticator.get({"challenge": "not-a-challenge"})},
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_login_with_an_enrolled_passkey_opens_a_session(
    authenticated_client: AsyncClient,
    authenticator: SoftAuthenticator,
    enrol_passkey: EnrolPasskey,
    test_db_session: AsyncSession,
) -> None:
    await enrol_passkey()
    authenticated_client.cookies.clear()

    options = await authenticated_client.post("/auth/passkeys/login/options")
    response = await authenticated_client.post(
        "/auth/passkeys/login",
        json={"credential": authenticator.get(options.json())},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "test_user"
    assert response.cookies["session_id"]

    stored = await test_db_session.scalar(
        select(PasskeyModel).where(
            PasskeyModel.credential_id == authenticator.credential_id
        )
    )
    assert stored is not None
    await test_db_session.refresh(stored)
    assert stored.sign_count == 1
    assert stored.last_used_at is not None


@pytest.mark.anyio
async def test_login_with_an_unregistered_credential_is_rejected(
    client: AsyncClient, authenticator: SoftAuthenticator
) -> None:
    options = await client.post("/auth/passkeys/login/options")

    response = await client.post(
        "/auth/passkeys/login",
        json={"credential": authenticator.get(options.json())},
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_login_is_refused_while_the_account_is_unconfirmed(
    authenticated_client: AsyncClient,
    authenticator: SoftAuthenticator,
    enrol_passkey: EnrolPasskey,
    test_db_session: AsyncSession,
) -> None:
    await enrol_passkey()
    authenticated_client.cookies.clear()

    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.username == "test_user")
    )
    assert db_user is not None
    db_user.is_active = False
    await test_db_session.commit()

    options = await authenticated_client.post("/auth/passkeys/login/options")
    response = await authenticated_client.post(
        "/auth/passkeys/login",
        json={"credential": authenticator.get(options.json())},
    )

    assert response.status_code == 401

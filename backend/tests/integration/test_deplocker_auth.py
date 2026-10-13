from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from email_validator import EmailUndeliverableError
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserModel
from app.schemas.auth import SessionData, UserRegisterResponse, UserRole
from app.utils.auth.confirmation import CONFIRMATION_WINDOW
from app.utils.auth.deplocker_auth import generate_jwt

REGISTER_PAYLOAD = {
    "username": "armir",
    "email": "armir.shehaj@gmail.com",
    "full_name": "Armir Shehaj",
    "password": "Armir2026!",
}
NEW_EMAIL = "armir.shehaj.new@gmail.com"


async def _backdate_signup(test_db_session: AsyncSession, email: str) -> None:
    """Moves the account's signup past its confirmation window."""
    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == email)
    )
    assert db_user is not None
    db_user.created_at = datetime.now() - CONFIRMATION_WINDOW - timedelta(minutes=1)
    await test_db_session.flush()


@pytest.mark.anyio
async def test_register(client: AsyncClient) -> None:
    response = await client.post("/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    response_data: dict = response.json()

    try:
        schema_object = UserRegisterResponse(**response_data)
        assert schema_object.message == (
            "Signup request successfully completed! "
            "You will shortly recieve a verification request in your email address..."
        )

    except ValidationError as e:
        pytest.fail(f"Response validation failed: {e.errors()}")


@pytest.mark.anyio
async def test_register_sends_confirmation_email(
    client: AsyncClient, mock_smtp: MagicMock
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)

    server = mock_smtp.return_value.__enter__.return_value
    server.send_message.assert_called_once()
    message = server.send_message.call_args.args[0]

    assert message["To"] == REGISTER_PAYLOAD["email"]
    assert (
        f"/account/confirm?email={REGISTER_PAYLOAD['email']}" in message.get_content()
    )


@pytest.mark.anyio
async def test_register_keeps_no_account_when_email_fails(
    client: AsyncClient, test_db_session: AsyncSession, mock_smtp: MagicMock
) -> None:
    mock_smtp.side_effect = ConnectionRefusedError()
    response = await client.post("/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 503
    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == REGISTER_PAYLOAD["email"])
    )
    assert db_user is None

    mock_smtp.side_effect = None
    response = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201


@pytest.mark.anyio
async def test_register_rejects_undeliverable_email(
    client: AsyncClient,
    test_db_session: AsyncSession,
    mock_smtp: MagicMock,
    mock_dns: MagicMock,
) -> None:
    mock_dns.side_effect = EmailUndeliverableError(
        "The domain name gmail.com does not exist."
    )
    response = await client.post("/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "The domain name gmail.com does not exist. Please check the email address."
    )
    mock_smtp.assert_not_called()
    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == REGISTER_PAYLOAD["email"])
    )
    assert db_user is None


@pytest.mark.anyio
async def test_resend_confirmation_email(
    client: AsyncClient, mock_smtp: MagicMock
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/auth/account/confirm/retry", params={"email": REGISTER_PAYLOAD["email"]}
    )

    assert response.status_code == 200
    server = mock_smtp.return_value.__enter__.return_value
    message = server.send_message.call_args.args[0]
    assert message["To"] == REGISTER_PAYLOAD["email"]


@pytest.mark.anyio
async def test_resend_confirmation_email_without_account(
    client: AsyncClient, mock_smtp: MagicMock
) -> None:
    response = await client.post(
        "/auth/account/confirm/retry", params={"email": REGISTER_PAYLOAD["email"]}
    )

    assert response.status_code == 404
    mock_smtp.assert_not_called()


@pytest.mark.anyio
async def test_resend_confirmation_email_after_release(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    await _backdate_signup(test_db_session, REGISTER_PAYLOAD["email"])

    response = await client.post(
        "/auth/account/confirm/retry", params={"email": REGISTER_PAYLOAD["email"]}
    )

    assert response.status_code == 410


@pytest.mark.anyio
async def test_register_ignores_requested_role(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    response = await client.post(
        "/auth/register", json={**REGISTER_PAYLOAD, "role": "owner"}
    )
    assert response.status_code == 201

    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == REGISTER_PAYLOAD["email"])
    )
    assert db_user is not None
    assert db_user.role == UserRole.USER


@pytest.mark.anyio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post("/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 409


@pytest.mark.anyio
async def test_register_duplicate_username(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/auth/register", json={**REGISTER_PAYLOAD, "email": NEW_EMAIL}
    )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_register_releases_unconfirmed_account(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    await _backdate_signup(test_db_session, REGISTER_PAYLOAD["email"])

    response = await client.get(
        "/auth/check-username", params={"username": REGISTER_PAYLOAD["username"]}
    )
    assert response.json() == {"available": True}

    response = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.email == REGISTER_PAYLOAD["email"])
    )
    assert db_user is not None
    assert db_user.created_at > datetime.now() - CONFIRMATION_WINDOW


@pytest.mark.anyio
async def test_login_unconfirmed_account(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)

    response = await client.post(
        "/auth/login",
        data={
            "username": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )

    assert response.status_code == 403
    assert response.json()["email"] == REGISTER_PAYLOAD["email"]
    assert "session_id" not in response.cookies


@pytest.mark.anyio
async def test_login_released_account(
    client: AsyncClient, test_db_session: AsyncSession
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    await _backdate_signup(test_db_session, REGISTER_PAYLOAD["email"])

    response = await client.post(
        "/auth/login",
        data={
            "username": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )

    assert response.status_code == 410


@pytest.mark.anyio
async def test_change_unconfirmed_email(
    client: AsyncClient, test_db_session: AsyncSession, mock_smtp: MagicMock
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)

    response = await client.post(
        "/auth/account/email",
        json={
            "identifier": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
            "email": NEW_EMAIL,
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == NEW_EMAIL
    server = mock_smtp.return_value.__enter__.return_value
    message = server.send_message.call_args.args[0]
    assert message["To"] == NEW_EMAIL

    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.username == REGISTER_PAYLOAD["username"])
    )
    assert db_user is not None
    assert db_user.email == NEW_EMAIL


@pytest.mark.anyio
async def test_change_unconfirmed_email_keeps_address_when_email_fails(
    client: AsyncClient, test_db_session: AsyncSession, mock_smtp: MagicMock
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    mock_smtp.side_effect = ConnectionRefusedError()

    response = await client.post(
        "/auth/account/email",
        json={
            "identifier": REGISTER_PAYLOAD["email"],
            "password": REGISTER_PAYLOAD["password"],
            "email": NEW_EMAIL,
        },
    )

    assert response.status_code == 503
    db_user = await test_db_session.scalar(
        select(UserModel).where(UserModel.username == REGISTER_PAYLOAD["username"])
    )
    assert db_user is not None
    assert db_user.email == REGISTER_PAYLOAD["email"]


@pytest.mark.anyio
async def test_change_unconfirmed_email_rejects_wrong_password(
    client: AsyncClient,
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)

    response = await client.post(
        "/auth/account/email",
        json={
            "identifier": REGISTER_PAYLOAD["username"],
            "password": "Wrong2026!",
            "email": NEW_EMAIL,
        },
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_change_email_of_confirmed_account(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    token = generate_jwt(sub=REGISTER_PAYLOAD["email"])
    await client.post(
        "/auth/account/confirm",
        params={"email": REGISTER_PAYLOAD["email"], "token": token},
    )

    response = await client.post(
        "/auth/account/email",
        json={
            "identifier": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
            "email": NEW_EMAIL,
        },
    )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_change_unconfirmed_email_to_taken_address(
    client: AsyncClient,
) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    await client.post(
        "/auth/register",
        json={**REGISTER_PAYLOAD, "username": "other", "email": NEW_EMAIL},
    )

    response = await client.post(
        "/auth/account/email",
        json={
            "identifier": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
            "email": NEW_EMAIL,
        },
    )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_login(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)

    token = generate_jwt(sub=REGISTER_PAYLOAD["email"])
    await client.post(
        "/auth/account/confirm",
        params={"email": REGISTER_PAYLOAD["email"], "token": token},
    )

    response = await client.post(
        "/auth/login",
        data={
            "username": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    assert response.status_code == 200

    response_data: dict = response.json()

    try:
        schema_object = SessionData(**response_data)
        assert type(schema_object.user_id) is int
        assert schema_object.email == REGISTER_PAYLOAD["email"]
        assert schema_object.role == UserRole.USER
        assert type(schema_object.created_at) is datetime

    except ValidationError as e:
        pytest.fail(f"Response validation failed: {e.errors()}")


@pytest.mark.anyio
async def test_session_check(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)

    token = generate_jwt(sub=REGISTER_PAYLOAD["email"])
    await client.post(
        "/auth/account/confirm",
        params={"email": REGISTER_PAYLOAD["email"], "token": token},
    )

    await client.post(
        "/auth/login",
        data={
            "username": REGISTER_PAYLOAD["username"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )

    # httpx keeps the session cookie and sends it back
    response = await client.get("/auth/session/check")
    assert response.status_code == 200

    response_data: dict = response.json()

    try:
        schema_object = SessionData(**response_data)
        assert type(schema_object.user_id) is int
        assert schema_object.username == REGISTER_PAYLOAD["username"]
        assert schema_object.role == UserRole.USER
        assert type(schema_object.created_at) is datetime

    except ValidationError as e:
        pytest.fail(f"Response validation failed: {e.errors()}")

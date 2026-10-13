from datetime import datetime
from typing import Any

import jwt
import pytest
from pydantic import ValidationError

from app.core.conf import settings
from app.schemas.auth import UserRegister
from app.utils.auth.deplocker_auth import (
    generate_jwt,
    get_password_hash,
    verify_password,
)


@pytest.fixture()
def test_user_register_payload() -> dict[str, str]:
    return {
        "username": "armir",
        "email": "armir.shehaj@gmail.com",
        "full_name": "Armir Shehaj",
        "password": "Armir2026!",
    }


@pytest.mark.anyio
def test_password_hash_is_not_plaintext() -> None:
    plain_password = "Armir2026!"
    hashed = get_password_hash(plain_password)
    assert hashed != plain_password


@pytest.mark.anyio
def test_password_hash_is_unique() -> None:
    plain_password = "Armir2026!"
    assert get_password_hash(plain_password) != get_password_hash(plain_password)


@pytest.mark.anyio
def test_verify_correct_password() -> None:
    plain_password = "Armir2026!"
    hashed = get_password_hash(plain_password)
    assert verify_password(plain_password, hashed) is True


@pytest.mark.anyio
def test_verify_incorrect_password() -> None:
    correct_password = "Armir2026!"
    hashed = get_password_hash(correct_password)
    wrong_password = "Armir2026"

    assert verify_password(wrong_password, hashed) is False


@pytest.mark.anyio
def test_generate_jwt() -> None:
    token = generate_jwt(sub="armir.shehaj@gmail.com", expire_minutes=15)

    decoded = jwt.decode(
        jwt=token, key=settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )

    assert decoded.get("sub") == "armir.shehaj@gmail.com"
    # JWT encodes "exp" as a Unix timestamp
    assert type(decoded.get("exp")) is int


@pytest.mark.anyio
def test_jwt_expiry() -> None:
    expire_minutes = 15
    before = datetime.now().timestamp()
    token = generate_jwt(sub="armir.shehaj@gmail.com", expire_minutes=expire_minutes)
    after = datetime.now().timestamp()

    decoded: dict[str, Any] = jwt.decode(
        token, key=settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )

    exp: int | None = decoded.get("exp")
    assert exp is not None
    assert int(before) + expire_minutes * 60 <= exp <= int(after) + expire_minutes * 60


@pytest.mark.anyio
def test_malformed_email_on_user_register(
    test_user_register_payload: dict[str, str],
) -> None:
    payload = test_user_register_payload
    payload["email"] = "armir.shehaj@"  # No domain

    with pytest.raises(ValidationError):
        UserRegister(**payload)

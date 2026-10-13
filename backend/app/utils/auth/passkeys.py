from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    options_to_json_dict,
    parse_registration_credential_json,
)
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core import redis
from app.core.conf import settings
from app.models import PasskeyModel, UserModel

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.auth import PasskeyRegistration


logger = logging.getLogger(__name__)

CHALLENGE_TTL = timedelta(minutes=5)
CHALLENGE_COOKIE = "passkey_challenge"


def _expired_challenge() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The passkey challenge has expired. Please try again.",
    )


async def _store_challenge(key: str, challenge: bytes) -> None:
    await redis.client.setex(key, CHALLENGE_TTL, bytes_to_base64url(challenge))


async def _pop_challenge(key: str) -> bytes:
    """Reads a challenge and burns it, so an assertion can only be played once."""
    stored: bytes | None = await redis.client.get(key)
    if stored is None:
        raise _expired_challenge()

    await redis.client.delete(key)
    return base64url_to_bytes(stored.decode())


def _registration_key(user_id: int) -> str:
    return f"passkey:registration:{user_id}"


def _authentication_key(handle: str) -> str:
    return f"passkey:authentication:{handle}"


def set_challenge_cookie(response: JSONResponse, handle: str) -> JSONResponse:
    """Login has no session to key the challenge on, so the handle to it rides
    along in a cookie rather than in the body the client would have to echo."""
    response.set_cookie(
        CHALLENGE_COOKIE,
        handle,
        httponly=True,
        secure=settings.ENVIRONMENT != "dev",
        samesite="strict",
        expires=int(CHALLENGE_TTL.total_seconds()),
    )
    return response


def get_challenge_handle(request: Request) -> str:
    handle = request.cookies.get(CHALLENGE_COOKIE)

    if not handle:
        raise _expired_challenge()

    return handle


async def build_registration_options(
    db_session: AsyncSession, db_user: UserModel
) -> dict[str, Any]:
    registered = await db_session.scalars(
        select(PasskeyModel.credential_id).where(PasskeyModel.user_id == db_user.id)
    )

    options = generate_registration_options(
        rp_id=settings.RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(db_user.id).encode(),
        user_name=db_user.username,
        user_display_name=db_user.full_name,
        # A discoverable credential carries the account with it, which is what
        # lets the login page offer a passkey before knowing who is signing in.
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=credential_id)
            for credential_id in registered
        ],
    )

    await _store_challenge(_registration_key(db_user.id), options.challenge)

    return options_to_json_dict(options)


async def register_passkey(
    db_session: AsyncSession, user_id: int, payload: PasskeyRegistration
) -> PasskeyModel:
    expected_challenge = await _pop_challenge(_registration_key(user_id))

    try:
        verification = verify_registration_response(
            credential=payload.credential,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.RP_ID,
            expected_origin=settings.FRONTEND_URL,
        )
        transports = (
            parse_registration_credential_json(payload.credential).response.transports
            or []
        )
    except (WebAuthnException, ValueError) as exc:
        logger.warning("Passkey registration rejected for user %s: %r", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The passkey could not be verified.",
        ) from exc

    new_passkey = PasskeyModel(
        user_id=user_id,
        name=payload.name,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=[transport.value for transport in transports],
    )

    try:
        db_session.add(new_passkey)
        await db_session.commit()
    except IntegrityError as exc:
        # `exclude_credentials` asks the authenticator not to re-enrol a passkey
        # it already holds, but nothing forces it to obey.
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This passkey is already registered.",
        ) from exc

    await db_session.refresh(new_passkey)
    return new_passkey


async def build_authentication_options() -> tuple[dict[str, Any], str]:
    options = generate_authentication_options(
        rp_id=settings.RP_ID, user_verification=UserVerificationRequirement.PREFERRED
    )

    handle = str(uuid.uuid4())
    await _store_challenge(_authentication_key(handle), options.challenge)

    return options_to_json_dict(options), handle


async def authenticate_passkey(
    db_session: AsyncSession, handle: str, credential: dict[str, Any]
) -> UserModel:
    """Resolve an assertion to the account that owns the credential it signed with.

    The credential id is unique across users, so the lookup alone identifies the
    account — the user handle the authenticator returns adds nothing to verify.
    """
    expected_challenge = await _pop_challenge(_authentication_key(handle))
    unverified = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Failed to authenticate with this passkey.",
    )

    try:
        credential_id = base64url_to_bytes(credential["rawId"])
    except (KeyError, TypeError, ValueError) as exc:
        raise unverified from exc

    db_passkey: PasskeyModel | None = await db_session.scalar(
        select(PasskeyModel)
        .where(PasskeyModel.credential_id == credential_id)
        .options(selectinload(PasskeyModel.user))
    )
    if db_passkey is None:
        logger.info("Assertion from an unregistered credential")
        raise unverified

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.RP_ID,
            expected_origin=settings.FRONTEND_URL,
            credential_public_key=db_passkey.public_key,
            credential_current_sign_count=db_passkey.sign_count,
        )
    except (WebAuthnException, ValueError) as exc:
        logger.warning(
            "Passkey assertion rejected for user %s: %r", db_passkey.user_id, exc
        )
        raise unverified from exc

    if not db_passkey.user.is_active:
        raise unverified

    db_passkey.sign_count = verification.new_sign_count
    db_passkey.last_used_at = func.now()
    await db_session.commit()

    return db_passkey.user

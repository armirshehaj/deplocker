from __future__ import annotations

import logging

# Kept out of TYPE_CHECKING: FastAPI evaluates these annotations to build the
# request signature, and an unresolved name fails only once a request arrives.
import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core.database import get_db_session
from app.models import PasskeyModel, UserModel
from app.schemas.auth import (
    PasskeyAuthentication,
    PasskeyRegistration,
    PasskeyResponse,
    SessionData,
)
from app.utils.auth.passkeys import (
    CHALLENGE_COOKIE,
    authenticate_passkey,
    build_authentication_options,
    build_registration_options,
    get_challenge_handle,
    register_passkey,
    set_challenge_cookie,
)
from app.utils.auth.shared import _login_response, get_current_session

from . import router

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


@router.post("/passkeys/register/options", summary="Start enrolling a new passkey")
async def passkey_registration_options(
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    db_user: UserModel | None = await db_session.get(UserModel, auth_session["user_id"])

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The account behind this session no longer exists.",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=await build_registration_options(db_session, db_user),
    )


@router.post(
    "/passkeys/register",
    summary="Finish enrolling a new passkey",
    status_code=status.HTTP_201_CREATED,
    response_model=PasskeyResponse,
)
async def passkey_registration(
    payload: PasskeyRegistration,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> PasskeyModel:
    return await register_passkey(db_session, auth_session["user_id"], payload)


@router.get(
    "/passkeys",
    summary="List the passkeys enrolled on the account",
    response_model=list[PasskeyResponse],
)
async def list_passkeys(
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> Sequence[PasskeyModel]:
    result = await db_session.scalars(
        select(PasskeyModel)
        .where(PasskeyModel.user_id == auth_session["user_id"])
        .order_by(PasskeyModel.created_at)
    )

    return result.all()


@router.delete(
    "/passkeys/{passkey_id}",
    summary="Remove an enrolled passkey",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_passkey(
    passkey_id: uuid.UUID,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    db_passkey: PasskeyModel | None = await db_session.scalar(
        select(PasskeyModel).where(
            PasskeyModel.id == passkey_id,
            PasskeyModel.user_id == auth_session["user_id"],
        )
    )

    if db_passkey is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passkey '{passkey_id}' was not found!",
        )

    await db_session.delete(db_passkey)
    await db_session.commit()


@router.post("/passkeys/login/options", summary="Start a passkey login")
async def passkey_authentication_options() -> JSONResponse:
    options, handle = await build_authentication_options()

    return set_challenge_cookie(
        JSONResponse(status_code=status.HTTP_200_OK, content=options), handle
    )


@router.post(
    "/passkeys/login", summary="Finish a passkey login", response_model=SessionData
)
async def passkey_login(
    payload: PasskeyAuthentication,
    handle: str = Depends(get_challenge_handle),
    db_session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    db_user = await authenticate_passkey(db_session, handle, payload.credential)

    db_user.last_login = func.now()
    await db_session.commit()

    session_data = SessionData(
        user_id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        role=db_user.role,
        created_at=db_user.created_at,
    )

    response = JSONResponse(
        status_code=status.HTTP_200_OK, content=session_data.model_dump(mode="json")
    )
    response.delete_cookie(CHALLENGE_COOKIE)

    return await _login_response(db_user, response)

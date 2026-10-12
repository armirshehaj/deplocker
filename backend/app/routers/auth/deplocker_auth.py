from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.responses import JSONResponse

# Kept out of TYPE_CHECKING: FastAPI evaluates these annotations to build the
# request signature, and an unresolved name fails only once a request arrives.
from fastapi.security import OAuth2PasswordRequestForm  # noqa: TC002
from pydantic import EmailStr  # noqa: TC002
from sqlalchemy import exists, func, not_, select

from app.core import redis
from app.core.conf import settings
from app.core.database import get_db_session
from app.models import UserModel
from app.schemas.auth import SessionData, UnconfirmedEmailChange, UserRegister
from app.utils.auth.confirmation import (
    delete_released_accounts,
    ensure_awaiting_confirmation,
    generate_confirmation_token,
    released_account,
)
from app.utils.auth.deplocker_auth import authenticate_user, get_password_hash
from app.utils.auth.shared import _add_default_organization, _login_response
from app.utils.email.confirmation import send_confirmation_email
from app.utils.email.deliverability import ensure_deliverable

from . import router

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


@router.get("/check-username")
async def check_username_availability(
    username: str, db_session: AsyncSession = Depends(get_db_session)
) -> dict[str, bool]:
    result = await db_session.execute(
        select(exists().where(UserModel.username == username, not_(released_account())))
    )

    return {"available": not result.scalar()}


@router.post("/register", summary="Register a new user in platform")
async def register_new_user(
    payload: UserRegister, db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    await delete_released_accounts(db_session)

    existing_email = await db_session.scalar(
        select(UserModel.email).where(UserModel.email == payload.email)
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{payload.email}' email already exists!",
        )

    existing_username = await db_session.scalar(
        select(UserModel.username).where(UserModel.username == payload.username)
    )
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{payload.username}' username is already taken!",
        )

    await ensure_deliverable(payload.email)

    new_user = UserModel(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password=get_password_hash(payload.password),
    )
    db_session.add(new_user)
    await db_session.flush()
    await _add_default_organization(db_session, new_user)

    jwt_token = generate_confirmation_token(new_user.email, datetime.now())
    try:
        await send_confirmation_email(new_user.email, jwt_token)
    except HTTPException:
        # Undoes the account, so the address can sign up again
        await db_session.rollback()
        raise

    await db_session.commit()

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message": (
                "Signup request successfully completed! "
                "You will shortly recieve a verification request in your email address..."
            ),
        },
    )


@router.post("/account/confirm", summary="Account activation endpoint")
async def confirm_new_account(
    email: EmailStr, token: str, db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    try:
        token_data: dict[str, Any] = jwt.decode(
            token, key=settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

    except jwt.ExpiredSignatureError as exc:
        await redis.client.set("expired_activation:email", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Activation token has expired. Please request a new confirmation email.",
        ) from exc

    subject: str | None = token_data.get("sub")

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Token failed to validate! Account could not be activated!",
        )

    db_user: UserModel | None = await db_session.scalar(
        select(UserModel).where(UserModel.email == subject)
    )

    if db_user:
        db_user.is_active = True
        await db_session.commit()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Account was successfully activated!"},
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account uses {subject}. Please sign up again.",
        )


@router.post("/account/confirm/retry")
async def resend_confirmation_email(
    email: EmailStr, db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
    db_user: UserModel | None = await db_session.scalar(
        select(UserModel).where(UserModel.email == email)
    )
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account uses {email}. Please sign up again.",
        )
    ensure_awaiting_confirmation(db_user)

    jwt_token = generate_confirmation_token(email, db_user.created_at)
    await send_confirmation_email(email, jwt_token)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "A new confirmation email was sent to your address."},
    )


@router.post(
    "/account/email",
    summary="Move an account awaiting confirmation to another email address",
)
async def change_unconfirmed_email(
    payload: UnconfirmedEmailChange,
    db_session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    db_user = await authenticate_user(db_session, payload.identifier, payload.password)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials were provided.",
        )
    ensure_awaiting_confirmation(db_user)

    await delete_released_accounts(db_session)
    email_taken = await db_session.scalar(
        select(
            exists().where(UserModel.email == payload.email, UserModel.id != db_user.id)
        )
    )
    if email_taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{payload.email}' email already exists!",
        )

    await ensure_deliverable(payload.email)

    db_user.email = payload.email
    jwt_token = generate_confirmation_token(payload.email, db_user.created_at)
    try:
        await send_confirmation_email(payload.email, jwt_token)
    except HTTPException:
        # Keeps the account on its previous address
        await db_session.rollback()
        raise

    await db_session.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": f"A new confirmation email was sent to {payload.email}.",
            "email": payload.email,
        },
    )


@router.post("/login", summary="Login endpoint", response_model=SessionData)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    db_user = await authenticate_user(
        db_session, form_data.username, form_data.password
    )

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate! Incorrect credentials were provided.",
        )

    if not db_user.is_active:
        ensure_awaiting_confirmation(db_user)
        # `email` lets the client offer to resend the link or change the address
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": (
                    "Your account is not confirmed yet. "
                    f"The confirmation link was sent to {db_user.email}."
                ),
                "email": db_user.email,
            },
        )

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
    return await _login_response(db_user, response)

import logging
from datetime import datetime, timedelta
from typing import cast

import jwt
from pwdlib import PasswordHash
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.models.auth import UserModel

password_hash = PasswordHash.recommended()

logger = logging.getLogger(__name__)


def get_password_hash(plain_password: str) -> str:
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def generate_jwt(
    sub: str, expire_minutes: int = settings.ACCESS_TOKEN_EXPIRES_MINUTES
) -> str:
    token_data = {"sub": sub, "exp": datetime.now() + timedelta(minutes=expire_minutes)}
    token = jwt.encode(
        payload=token_data, key=settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return token


async def get_user_by_identifier(
    db_session: AsyncSession, identifier: str
) -> UserModel | None:
    return cast(
        "UserModel | None",
        await db_session.scalar(
            select(UserModel).where(
                or_(UserModel.username == identifier, UserModel.email == identifier)
            )
        ),
    )


async def authenticate_user(
    db_session: AsyncSession, identifier: str, plain_password: str
) -> UserModel | None:
    """Returns the account the credentials belong to, confirmed or not."""
    db_user: UserModel | None = await get_user_by_identifier(db_session, identifier)

    if db_user is None:
        return None

    is_password_valid = verify_password(plain_password, db_user.password)
    if not is_password_valid:
        return None

    return db_user

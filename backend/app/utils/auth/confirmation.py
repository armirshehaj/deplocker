from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, or_, select

from app.models import OrganizationMembersModel, OrganizationModel, UserModel
from app.utils.auth.deplocker_auth import generate_jwt

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement
    from sqlalchemy.ext.asyncio import AsyncSession

# An account left unconfirmed this long after signup is released: its username
# and email address can sign up again
CONFIRMATION_WINDOW = timedelta(hours=24)


def generate_confirmation_token(email: str, signed_up_at: datetime) -> str:
    """Signs a confirmation link that expires with the account's confirmation window."""
    remaining = signed_up_at + CONFIRMATION_WINDOW - datetime.now()
    return generate_jwt(sub=email, expire_minutes=int(remaining.total_seconds() // 60))


def ensure_awaiting_confirmation(user: UserModel) -> None:
    """Answers 409 for a confirmed account and 410 for one released unconfirmed."""
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already confirmed! Please, sign in.",
        )

    if user.created_at + CONFIRMATION_WINDOW <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This account was not confirmed within 24 hours of signing up, "
                "so it was removed. Please sign up again."
            ),
        )


def released_account() -> ColumnElement[bool]:
    """Matches the accounts left unconfirmed past their confirmation window."""
    return and_(
        UserModel.is_active.is_(False),
        UserModel.created_at <= datetime.now() - CONFIRMATION_WINDOW,
    )


async def delete_released_accounts(db_session: AsyncSession) -> None:
    """Deletes the released accounts with their default organizations, freeing
    their usernames and email addresses."""
    user_ids = list(
        await db_session.scalars(select(UserModel.id).where(released_account()))
    )
    if not user_ids:
        return

    organization_ids = select(OrganizationModel.id).where(
        OrganizationModel.owner_id.in_(user_ids)
    )
    await db_session.execute(
        delete(OrganizationMembersModel).where(
            or_(
                OrganizationMembersModel.user_id.in_(user_ids),
                OrganizationMembersModel.organization_id.in_(organization_ids),
            )
        )
    )
    await db_session.execute(
        delete(OrganizationModel).where(OrganizationModel.owner_id.in_(user_ids))
    )
    await db_session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))

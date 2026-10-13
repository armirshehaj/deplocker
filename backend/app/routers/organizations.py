import logging
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.organizations import OrganizationMembersModel, OrganizationModel
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationRole,
    OrganizationSummary,
)
from app.utils.auth.shared import get_current_session
from app.utils.naming.conflicts import commit_unless_name_taken
from app.utils.text.slug_generator import generate_slug

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/create",
    summary="New organization creation endpoint",
    response_model=OrganizationResponse,
)
async def create_organization(
    payload: OrganizationCreate,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> OrganizationModel:
    slug = generate_slug(payload.name)
    new_organization = OrganizationModel(
        owner_id=auth_session["user_id"], name=payload.name, slug=slug
    )
    db_session.add(new_organization)
    await commit_unless_name_taken(
        db_session, f"The slug '{slug}' is already taken by another organization!"
    )
    await db_session.refresh(new_organization)

    new_org_member = OrganizationMembersModel(
        user_id=auth_session["user_id"],
        organization_id=new_organization.id,
        role=OrganizationRole.OWNER,
    )
    db_session.add(new_org_member)
    await db_session.commit()

    return new_organization


@router.get(
    "",
    summary="Get all organizations the caller belongs to",
    response_model=list[OrganizationSummary],
)
async def get_user_organizations(
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> Sequence[Row[tuple[uuid.UUID, str, str]]]:
    result = await db_session.execute(
        select(OrganizationModel.id, OrganizationModel.name, OrganizationModel.slug)
        .join(
            OrganizationMembersModel,
            OrganizationMembersModel.organization_id == OrganizationModel.id,
        )
        .where(OrganizationMembersModel.user_id == auth_session["user_id"])
        .order_by(OrganizationMembersModel.joined_at)
    )
    return result.all()

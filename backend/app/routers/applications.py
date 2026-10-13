import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.applications import ApplicationModel
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.schemas.organizations import OrganizationRole
from app.utils.auth.shared import get_current_session
from app.utils.naming.conflicts import commit_unless_name_taken
from app.utils.organizations.membership import (
    get_member_application,
    get_member_project,
    select_member_applications,
)
from app.utils.organizations.roles import require_role
from app.utils.text.slug_generator import generate_slug

router = APIRouter()


@router.post(
    "",
    summary="Application creation endpoint",
    status_code=201,
    response_model=ApplicationResponse,
)
async def create_application(
    payload: ApplicationCreate,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> ApplicationModel:
    await get_member_project(
        db_session, auth_session["user_id"], payload.project_id, OrganizationRole.ADMIN
    )

    new_application = ApplicationModel(
        name=payload.name,
        slug=generate_slug(payload.name),
        project_id=payload.project_id,
        description=payload.description,
        git_url=payload.git_url,
        branch=payload.branch,
        dockerfile_path=payload.dockerfile_path,
        port=payload.port,
        env_vars=payload.env_vars,
        domain=payload.domain,
    )

    db_session.add(new_application)
    await commit_unless_name_taken(
        db_session, f"The name '{payload.name}' is already taken in this project!"
    )
    await db_session.refresh(new_application)

    return new_application


@router.get(
    "",
    summary="List applications, optionally filtered by name",
    response_model=list[ApplicationResponse],
)
async def list_applications(
    name: str | None = None,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> Sequence[ApplicationModel]:
    query = select_member_applications(auth_session["user_id"])

    if name is not None:
        query = query.where(ApplicationModel.name == name)

    result = await db_session.execute(query)
    return result.scalars().all()


@router.get(
    "/{id}",
    summary="Get application by ID",
    response_model=ApplicationResponse,
)
async def get_application_by_id(
    id: uuid.UUID,
    auth_session: dict = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
) -> ApplicationModel:
    return await get_member_application(db_session, auth_session["user_id"], id)


@router.patch(
    "/{id}",
    summary="Application details update endpoint",
    response_model=ApplicationResponse,
)
async def update_application(
    payload: ApplicationUpdate,
    app_record: ApplicationModel = Depends(
        require_role(get_member_application, OrganizationRole.ADMIN)
    ),
    db_session: AsyncSession = Depends(get_db_session),
) -> ApplicationModel:
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(app_record, field, value)

    if payload.name is not None:
        app_record.slug = generate_slug(payload.name)

    await commit_unless_name_taken(
        db_session, f"The name '{payload.name}' is already taken in this project!"
    )
    await db_session.refresh(app_record)

    return app_record


@router.delete(
    "/{id}",
    status_code=204,
    summary="Project deletion endpoint",
)
async def delete_application(
    app_record: ApplicationModel = Depends(
        require_role(get_member_application, OrganizationRole.OWNER)
    ),
    db_session: AsyncSession = Depends(get_db_session),
) -> None:
    await db_session.delete(app_record)
    await db_session.commit()

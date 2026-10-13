import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applications import ApplicationModel
from app.models.deployments import DeploymentModel
from app.models.organizations import OrganizationMembersModel
from app.models.projects import ProjectModel
from app.schemas.organizations import OrganizationRole
from app.utils.organizations.roles import ensure_role


# The helpers below answer 404 for a resource outside the caller's organizations,
# so the response does not reveal whether it exists, and 403 to a member below
# `required_role` (see `ensure_role`).
async def ensure_organization_member(
    db_session: AsyncSession,
    user_id: int,
    organization_id: uuid.UUID,
    required_role: OrganizationRole = OrganizationRole.MEMBER,
) -> None:
    role = await db_session.scalar(
        select(OrganizationMembersModel.role).where(
            OrganizationMembersModel.user_id == user_id,
            OrganizationMembersModel.organization_id == organization_id,
        )
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{organization_id}' was not found!",
        )

    ensure_role(role, required_role)


def select_member_projects(user_id: int) -> Select[tuple[ProjectModel]]:
    return (
        select(ProjectModel)
        .join(
            OrganizationMembersModel,
            OrganizationMembersModel.organization_id == ProjectModel.organization_id,
        )
        .where(OrganizationMembersModel.user_id == user_id)
    )


def select_member_applications(user_id: int) -> Select[tuple[ApplicationModel]]:
    return (
        select(ApplicationModel)
        .join(ProjectModel, ProjectModel.id == ApplicationModel.project_id)
        .join(
            OrganizationMembersModel,
            OrganizationMembersModel.organization_id == ProjectModel.organization_id,
        )
        .where(OrganizationMembersModel.user_id == user_id)
    )


def select_member_deployments(user_id: int) -> Select[tuple[DeploymentModel]]:
    return (
        select(DeploymentModel)
        .join(ApplicationModel, ApplicationModel.id == DeploymentModel.application_id)
        .join(ProjectModel, ProjectModel.id == ApplicationModel.project_id)
        .join(
            OrganizationMembersModel,
            OrganizationMembersModel.organization_id == ProjectModel.organization_id,
        )
        .where(OrganizationMembersModel.user_id == user_id)
    )


async def get_member_project(
    db_session: AsyncSession,
    user_id: int,
    project_id: uuid.UUID,
    required_role: OrganizationRole = OrganizationRole.MEMBER,
) -> ProjectModel:
    query: Select[tuple[ProjectModel, OrganizationRole]] = (
        select_member_projects(user_id)
        .add_columns(OrganizationMembersModel.role)
        .where(ProjectModel.id == project_id)
    )
    found = (await db_session.execute(query)).tuples().one_or_none()
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' was not found!",
        )

    project_record, role = found
    ensure_role(role, required_role)
    return project_record


async def get_member_application(
    db_session: AsyncSession,
    user_id: int,
    application_id: uuid.UUID,
    required_role: OrganizationRole = OrganizationRole.MEMBER,
) -> ApplicationModel:
    query: Select[tuple[ApplicationModel, OrganizationRole]] = (
        select_member_applications(user_id)
        .add_columns(OrganizationMembersModel.role)
        .where(ApplicationModel.id == application_id)
    )
    found = (await db_session.execute(query)).tuples().one_or_none()
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' was not found!",
        )

    application_record, role = found
    ensure_role(role, required_role)
    return application_record


async def get_member_deployment(
    db_session: AsyncSession,
    user_id: int,
    deployment_id: uuid.UUID,
    required_role: OrganizationRole = OrganizationRole.MEMBER,
) -> DeploymentModel:
    query: Select[tuple[DeploymentModel, OrganizationRole]] = (
        select_member_deployments(user_id)
        .add_columns(OrganizationMembersModel.role)
        .where(DeploymentModel.id == deployment_id)
    )
    found = (await db_session.execute(query)).tuples().one_or_none()
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment '{deployment_id}' was not found!",
        )

    deployment_record, role = found
    ensure_role(role, required_role)
    return deployment_record

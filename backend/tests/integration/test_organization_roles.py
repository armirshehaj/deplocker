"""Each organization role holds the powers of those below it: a MEMBER reads
and deploys, an ADMIN also creates and changes projects and applications, and
an OWNER also deletes them and their deployments. A member below the required
role gets a 403 rather than a 404: they can already read the resource, so there
is nothing to hide."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApplicationModel,
    DeploymentModel,
    OrganizationMembersModel,
    ProjectModel,
)
from app.schemas.organizations import OrganizationRole

MODELS: dict[str, type[ProjectModel | ApplicationModel | DeploymentModel]] = {
    "projects": ProjectModel,
    "applications": ApplicationModel,
    "deployments": DeploymentModel,
}


@pytest.fixture()
async def resources(
    authenticated_client: AsyncClient,
    project_factory: Callable[..., Awaitable[Response]],
    application_create_test: Response,
) -> dict[str, uuid.UUID]:
    """One resource of each kind in the test user's default organization. The
    project is not the application's, so deleting it cascades to nothing."""
    project_response = await project_factory(
        name="Disposable", description="Has no applications."
    )
    deployment_response = await authenticated_client.post(
        "/deployments", json={"application_id": application_create_test.json()["id"]}
    )
    assert deployment_response.status_code == 201

    return {
        "projects": uuid.UUID(project_response.json()["id"]),
        "applications": uuid.UUID(application_create_test.json()["id"]),
        "deployments": uuid.UUID(deployment_response.json()["id"]),
    }


@pytest.fixture()
async def new_resource_payloads(
    default_organization_id: uuid.UUID, resources: dict[str, uuid.UUID]
) -> dict[str, dict[str, Any]]:
    return {
        "projects": {
            "name": "New project",
            "description": "A new project.",
            "organization_id": str(default_organization_id),
        },
        "applications": {
            "project_id": str(resources["projects"]),
            "name": "New application",
            "description": "A new application.",
            "git_url": "https://github.com/armir-eng/deplocker-api",
            "env_vars": {},
            "domain": "new-application.deplocker.com",
        },
        "deployments": {"application_id": str(resources["applications"])},
    }


@pytest.fixture()
async def assign_role(
    test_db_session: AsyncSession, default_organization_id: uuid.UUID
) -> Callable[[OrganizationRole], Awaitable[None]]:
    """Sets the test user's role in their default organization, which they
    are the only member of."""

    async def assign(role: OrganizationRole) -> None:
        await test_db_session.execute(
            update(OrganizationMembersModel)
            .where(OrganizationMembersModel.organization_id == default_organization_id)
            .values(role=role)
        )

    return assign


@pytest.mark.anyio
@pytest.mark.parametrize("role", list(OrganizationRole))
@pytest.mark.parametrize("resource", ["projects", "applications", "deployments"])
async def test_any_member_can_read(
    authenticated_client: AsyncClient,
    resources: dict[str, uuid.UUID],
    assign_role: Callable[[OrganizationRole], Awaitable[None]],
    resource: str,
    role: OrganizationRole,
) -> None:
    await assign_role(role)

    response = await authenticated_client.get(f"/{resource}/{resources[resource]}")
    assert response.status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("role", list(OrganizationRole))
async def test_any_member_can_deploy(
    authenticated_client: AsyncClient,
    new_resource_payloads: dict[str, dict[str, Any]],
    assign_role: Callable[[OrganizationRole], Awaitable[None]],
    role: OrganizationRole,
) -> None:
    await assign_role(role)

    response = await authenticated_client.post(
        "/deployments", json=new_resource_payloads["deployments"]
    )
    assert response.status_code == 201


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "status_code"),
    [
        (OrganizationRole.OWNER, 201),
        (OrganizationRole.ADMIN, 201),
        (OrganizationRole.MEMBER, 403),
    ],
)
@pytest.mark.parametrize("resource", ["projects", "applications"])
async def test_create_requires_admin(
    authenticated_client: AsyncClient,
    new_resource_payloads: dict[str, dict[str, Any]],
    assign_role: Callable[[OrganizationRole], Awaitable[None]],
    resource: str,
    role: OrganizationRole,
    status_code: int,
) -> None:
    await assign_role(role)

    response = await authenticated_client.post(
        f"/{resource}", json=new_resource_payloads[resource]
    )
    assert response.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "status_code"),
    [
        (OrganizationRole.OWNER, 200),
        (OrganizationRole.ADMIN, 200),
        (OrganizationRole.MEMBER, 403),
    ],
)
@pytest.mark.parametrize("resource", ["projects", "applications"])
async def test_update_requires_admin(
    authenticated_client: AsyncClient,
    test_db_session: AsyncSession,
    resources: dict[str, uuid.UUID],
    assign_role: Callable[[OrganizationRole], Awaitable[None]],
    resource: str,
    role: OrganizationRole,
    status_code: int,
) -> None:
    await assign_role(role)

    response = await authenticated_client.patch(
        f"/{resource}/{resources[resource]}",
        json={"name": "Renamed", "description": "Renamed."},
    )
    assert response.status_code == status_code

    stored = await test_db_session.get(
        MODELS[resource], resources[resource], populate_existing=True
    )
    assert isinstance(stored, ProjectModel | ApplicationModel)
    assert (stored.name == "Renamed") == (status_code == 200)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("role", "status_code"),
    [
        (OrganizationRole.OWNER, 204),
        (OrganizationRole.ADMIN, 403),
        (OrganizationRole.MEMBER, 403),
    ],
)
@pytest.mark.parametrize("resource", ["projects", "applications", "deployments"])
async def test_delete_requires_owner(
    authenticated_client: AsyncClient,
    test_db_session: AsyncSession,
    resources: dict[str, uuid.UUID],
    assign_role: Callable[[OrganizationRole], Awaitable[None]],
    resource: str,
    role: OrganizationRole,
    status_code: int,
) -> None:
    await assign_role(role)

    response = await authenticated_client.delete(f"/{resource}/{resources[resource]}")
    assert response.status_code == status_code

    stored = await test_db_session.get(
        MODELS[resource], resources[resource], populate_existing=True
    )
    assert (stored is None) == (status_code == 204)

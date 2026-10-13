"""The test user's default organization against a foreign one: every route
answers 404 for a resource across the boundary, so its existence isn't
confirmed, and leaves the resource untouched."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationModel, DeploymentModel, ProjectModel


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "resource", "body"),
    [
        ("GET", "projects", None),
        ("PATCH", "projects", {"name": "Hijacked", "description": "Hijacked"}),
        ("DELETE", "projects", None),
        ("GET", "applications", None),
        ("PATCH", "applications", {"name": "Hijacked"}),
        ("DELETE", "applications", None),
        ("GET", "deployments", None),
        ("DELETE", "deployments", None),
    ],
)
async def test_foreign_resource_is_not_found(
    authenticated_client: AsyncClient,
    test_db_session: AsyncSession,
    foreign_project: ProjectModel,
    foreign_application: ApplicationModel,
    foreign_deployment: DeploymentModel,
    method: str,
    resource: str,
    body: dict[str, Any] | None,
) -> None:
    records: dict[str, ProjectModel | ApplicationModel | DeploymentModel] = {
        "projects": foreign_project,
        "applications": foreign_application,
        "deployments": foreign_deployment,
    }
    record = records[resource]

    response = await authenticated_client.request(
        method, f"/{resource}/{record.id}", json=body
    )
    assert response.status_code == 404

    stored = await test_db_session.get(type(record), record.id, populate_existing=True)
    assert stored is not None
    if body is not None:
        assert isinstance(stored, ProjectModel | ApplicationModel)
        assert stored.name != body["name"]


@pytest.mark.anyio
async def test_create_project_in_foreign_organization(
    authenticated_client: AsyncClient, foreign_project: ProjectModel
) -> None:
    payload = {
        "name": "Deplocker",
        "description": "Easily deploy and scale your dockerized projects.",
        "organization_id": str(foreign_project.organization_id),
    }

    response = await authenticated_client.post("/projects", json=payload)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_project_in_nonexistent_organization(
    authenticated_client: AsyncClient,
) -> None:
    payload = {
        "name": "Deplocker",
        "description": "Easily deploy and scale your dockerized projects.",
        "organization_id": str(uuid.uuid4()),
    }

    # Answers the same as a foreign organization, so the two can't be told apart.
    response = await authenticated_client.post("/projects", json=payload)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_application_in_foreign_project(
    authenticated_client: AsyncClient, foreign_project: ProjectModel
) -> None:
    payload = {
        "project_id": str(foreign_project.id),
        "name": "Deplocker API",
        "description": "Deplocker Backend",
        "git_url": "https://github.com/armir-eng/deplocker-api",
        "env_vars": {},
        "domain": "deplocker-api.armir.dev",
    }

    response = await authenticated_client.post("/applications", json=payload)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_deployment_of_foreign_application(
    authenticated_client: AsyncClient, foreign_application: ApplicationModel
) -> None:
    response = await authenticated_client.post(
        "/deployments", json={"application_id": str(foreign_application.id)}
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_list_projects_of_foreign_organization(
    authenticated_client: AsyncClient, foreign_project: ProjectModel
) -> None:
    response = await authenticated_client.get(
        "/projects", params={"org_id": str(foreign_project.organization_id)}
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_project_by_name_of_foreign_organization(
    authenticated_client: AsyncClient,
    default_organization_id: uuid.UUID,
    foreign_project: ProjectModel,
) -> None:
    response = await authenticated_client.get(
        "/projects",
        params={"org_id": str(default_organization_id), "name": foreign_project.name},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_applications_leaves_out_foreign_ones(
    authenticated_client: AsyncClient,
    application_create_test: Response,
    foreign_application: ApplicationModel,
) -> None:
    response = await authenticated_client.get("/applications")
    assert response.status_code == 200
    assert [a["id"] for a in response.json()] == [application_create_test.json()["id"]]


@pytest.mark.anyio
async def test_get_application_by_name_of_foreign_organization(
    authenticated_client: AsyncClient, foreign_application: ApplicationModel
) -> None:
    response = await authenticated_client.get(
        "/applications", params={"name": foreign_application.name}
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_list_deployments_leaves_out_foreign_ones(
    authenticated_client: AsyncClient,
    application_create_test: Response,
    foreign_deployment: DeploymentModel,
) -> None:
    create_response = await authenticated_client.post(
        "/deployments", json={"application_id": application_create_test.json()["id"]}
    )
    assert create_response.status_code == 201

    response = await authenticated_client.get("/deployments/")
    assert response.status_code == 200
    assert [d["id"] for d in response.json()] == [create_response.json()["id"]]


# Names are unique per organization (projects) and per project (applications),
# so a name taken across the boundary is free to use, and a 409 for it would
# confirm that it exists elsewhere.
@pytest.mark.anyio
async def test_create_project_with_foreign_project_name(
    authenticated_client: AsyncClient,
    default_organization_id: uuid.UUID,
    foreign_project: ProjectModel,
) -> None:
    payload = {
        "name": foreign_project.name,
        "description": "Same name as a project in another organization.",
        "organization_id": str(default_organization_id),
    }

    response = await authenticated_client.post("/projects", json=payload)
    assert response.status_code == 201
    assert response.json()["slug"] == foreign_project.slug


@pytest.mark.anyio
async def test_create_application_with_foreign_application_name(
    authenticated_client: AsyncClient,
    project_create_test: Response,
    foreign_application: ApplicationModel,
) -> None:
    payload = {
        "project_id": project_create_test.json()["id"],
        "name": foreign_application.name,
        "description": "Same name as an application in another organization.",
        "git_url": "https://github.com/armir-eng/deplocker-api",
        "env_vars": {},
        "domain": "own-application.deplocker.com",
    }

    response = await authenticated_client.post("/applications", json=payload)
    assert response.status_code == 201
    assert response.json()["slug"] == foreign_application.slug

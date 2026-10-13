import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from httpx import AsyncClient, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import redis
from app.models import (
    ApplicationModel,
    DeploymentModel,
    OrganizationMembersModel,
    OrganizationModel,
    ProjectModel,
    UserModel,
)
from app.schemas.applications import ApplicationResponse
from app.schemas.projects import ProjectResponse
from app.utils.auth.deplocker_auth import generate_jwt

AUTH_TEST_USER = {
    "username": "test_user",
    "email": "test.user@deplocker.com",
    "full_name": "Test User",
    "password": "TestUser2026!",
}


@pytest.fixture()
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Registers, confirms and logs in a test user, leaving `client` holding
    a valid `session_id` cookie for requests against protected routes."""

    await client.post("/auth/register", json=AUTH_TEST_USER)

    token = generate_jwt(sub=AUTH_TEST_USER["email"])
    await client.post(
        "/auth/account/confirm",
        params={"email": AUTH_TEST_USER["email"], "token": token},
    )

    login_response = await client.post(
        "/auth/login",
        data={
            "username": AUTH_TEST_USER["username"],
            "password": AUTH_TEST_USER["password"],
        },
    )

    assert login_response.status_code == 200

    return client


@pytest.fixture()
async def default_organization_id(
    authenticated_client: AsyncClient, test_db_session: AsyncSession
) -> uuid.UUID:
    """The test user's default organization, created on registration."""
    organization_id = await test_db_session.scalar(
        select(OrganizationMembersModel.organization_id)
        .join(UserModel, UserModel.id == OrganizationMembersModel.user_id)
        .where(UserModel.username == AUTH_TEST_USER["username"])
    )
    assert organization_id is not None
    return organization_id


@pytest.fixture()
async def project_factory(
    authenticated_client: AsyncClient, default_organization_id: uuid.UUID
) -> Callable[..., Awaitable[Response]]:
    async def create(name: str, description: str) -> Response:
        payload = {
            "name": name,
            "description": description,
            "organization_id": str(default_organization_id),
        }
        response: Response = await authenticated_client.post("/projects", json=payload)
        assert response.status_code == 201

        try:
            response_data = response.json()
            schema_object = ProjectResponse(**response_data)
            assert schema_object.name == name
            assert schema_object.description == description
            assert schema_object.organization_id == default_organization_id
            assert type(schema_object.id) is uuid.UUID

        except ValidationError as e:
            pytest.fail(f"Response validation failed: {e.errors()}")

        return response

    return create


@pytest.fixture()
async def project_create_test(
    project_factory: Callable[..., Awaitable[Response]],
) -> Response:
    response: Response = await project_factory(
        name="Deplocker",
        description="Easily deploy and scale your dockerized projects.",
    )

    return response


@pytest.fixture()
async def foreign_project(test_db_session: AsyncSession) -> ProjectModel:
    """A project in an organization the test user is not a member of."""
    owner = UserModel(
        username="foreign_user",
        email="foreign.user@deplocker.com",
        full_name="Foreign User",
        password="not-a-real-hash",
    )
    test_db_session.add(owner)
    await test_db_session.flush()

    organization = OrganizationModel(
        owner_id=owner.id, name="Foreign organization", slug="foreign-organization"
    )
    test_db_session.add(organization)
    await test_db_session.flush()

    test_db_session.add(
        OrganizationMembersModel(user_id=owner.id, organization_id=organization.id)
    )
    project = ProjectModel(
        organization_id=organization.id,
        name="Foreign project",
        slug="foreign-project",
        description="Belongs to another organization.",
    )
    test_db_session.add(project)
    await test_db_session.flush()

    return project


@pytest.fixture()
async def foreign_application(
    test_db_session: AsyncSession, foreign_project: ProjectModel
) -> ApplicationModel:
    """An application under `foreign_project`."""
    application = ApplicationModel(
        project_id=foreign_project.id,
        name="Foreign application",
        slug="foreign-application",
        description="Belongs to another organization.",
        git_url="https://github.com/foreign-user/foreign-application",
        env_vars={},
        domain="foreign-application.deplocker.com",
    )
    test_db_session.add(application)
    await test_db_session.flush()

    return application


@pytest.fixture()
async def foreign_deployment(
    test_db_session: AsyncSession, foreign_application: ApplicationModel
) -> DeploymentModel:
    """A deployment of `foreign_application`."""
    deployment = DeploymentModel(application_id=foreign_application.id)
    test_db_session.add(deployment)
    await test_db_session.flush()

    return deployment


# Creates an application in the test project, checking the response and the
# defaults it applies
@pytest.fixture()
async def application_factory(
    authenticated_client: AsyncClient, project_create_test: Response
) -> Callable[..., Awaitable[Response]]:
    async def create(
        name: str, description: str, git_url: str, env_vars: dict[str, Any], domain: str
    ) -> Response:
        created_project_id = project_create_test.json()["id"]
        payload = {
            "project_id": created_project_id,
            "name": name,
            "description": description,
            "git_url": git_url,
            "env_vars": env_vars,
            "domain": domain,
        }

        response: Response = await authenticated_client.post(
            "/applications", json=payload
        )
        assert response.status_code == 201

        try:
            response_data = response.json()
            schema_object = ApplicationResponse(**response_data)

            assert str(schema_object.project_id) == created_project_id
            assert schema_object.name == response_data["name"]
            assert schema_object.description == response_data["description"]
            assert schema_object.git_url == response_data["git_url"]
            assert schema_object.env_vars == response_data["env_vars"]
            assert schema_object.domain == response_data["domain"]

            # Defaults for the fields the payload leaves out
            assert schema_object.branch == "main"
            assert schema_object.dockerfile_path == "./Dockerfile"
            assert schema_object.port == 8000
            assert schema_object.desired_replicas == 1

        except ValidationError as e:
            pytest.fail(f"Response validation failed: {e.errors()}")

        return response

    return create


# The application the read, update and delete tests act on
@pytest.fixture()
async def application_create_test(
    application_factory: Callable[..., Awaitable[Response]],
) -> Response:
    payload = {
        "name": "Deplocker API",
        "description": "Deplocker Backend",
        "git_url": "https://github.com/armir-eng/deplocker-api",
        "env_vars": {
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "cebeda3044e47ac8eb20b0990353a0b87aa62e45d69f8f3b402bff6cd40dedcb",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": 5432,
        },
        "domain": "deplocker-api.armir.dev",
    }

    response: Response = await application_factory(**payload)
    return response


@pytest.fixture(autouse=True)
def mock_smtp() -> Generator[MagicMock, None, None]:
    """Stands in for the SMTP server; the emails sent reach the `send_message` of
    `mock_smtp.return_value.__enter__.return_value`."""
    with patch("smtplib.SMTP") as smtp:
        yield smtp


@pytest.fixture(autouse=True)
def mock_dns() -> Generator[MagicMock, None, None]:
    """Stands in for the DNS lookup of an address's domain, which accepts email
    unless a test gives `mock_dns` a side effect."""
    with patch(
        "email_validator.deliverability.validate_email_deliverability",
        return_value={"mx": [(10, "mx.deplocker.com")], "mx_fallback_type": None},
    ) as lookup:
        yield lookup


@pytest.fixture(autouse=True)
async def mock_redis() -> AsyncGenerator[None, None]:
    fake = fakeredis.aioredis.FakeRedis()
    original = redis.client
    redis.client = fake
    yield
    await fake.aclose()
    redis.client = original

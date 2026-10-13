import uuid
from collections.abc import Callable

import pytest
from faker import Faker
from httpx import AsyncClient, Response
from pydantic import ValidationError

from app.core import redis
from app.schemas.applications import ApplicationResponse

fake = Faker()
APPLICATION_ID = uuid.UUID(int=0)
APPLICATION_ROUTES = [
    ("POST", "/applications"),
    ("GET", "/applications"),
    ("GET", f"/applications/{APPLICATION_ID}"),
    ("PATCH", f"/applications/{APPLICATION_ID}"),
    ("DELETE", f"/applications/{APPLICATION_ID}"),
]


@pytest.mark.anyio
async def test_list_applications(
    application_factory: Callable, authenticated_client: AsyncClient
) -> None:
    for _ in range(10):
        await application_factory(
            name=fake.name(),
            description=fake.sentence(),
            git_url=fake.url(),
            env_vars={"DB_USER": fake.user_name(), "DB_PASSWORD": fake.password()},
            domain=fake.domain_name(),
        )

    response = await authenticated_client.get("/applications")
    response_data = response.json()
    assert type(response_data) is list
    assert len(response_data) == 10


@pytest.mark.anyio
async def test_get_application_by_id(
    application_create_test: Response, authenticated_client: AsyncClient
) -> None:
    new_application_data = application_create_test.json()
    new_application_id = new_application_data["id"]

    response = await authenticated_client.get(f"/applications/{new_application_id}")
    assert response.status_code == 200

    try:
        response_data = response.json()
        schema_object = ApplicationResponse(**response_data)

        assert str(schema_object.project_id) == new_application_data["project_id"]
        assert schema_object.name == new_application_data["name"]
        assert schema_object.description == new_application_data["description"]
        assert schema_object.git_url == new_application_data["git_url"]
        assert schema_object.env_vars == new_application_data["env_vars"]
        assert schema_object.domain == new_application_data["domain"]

        # Defaults for the fields the payload leaves out
        assert schema_object.branch == "main"
        assert schema_object.dockerfile_path == "./Dockerfile"
        assert schema_object.port == 8000
        assert schema_object.desired_replicas == 1

    except ValidationError as e:
        pytest.fail(f"Response validation failed: {e.errors()}")


# "deplocker-api" is a different name, but shares the existing application's slug.
@pytest.mark.anyio
@pytest.mark.parametrize("name", ["Deplocker API", "deplocker-api"])
async def test_create_application_with_taken_name(
    authenticated_client: AsyncClient, application_create_test: Response, name: str
) -> None:
    existing_application = application_create_test.json()
    assert existing_application["name"] == "Deplocker API"

    payload = {
        "project_id": existing_application["project_id"],
        "name": name,
        "description": fake.sentence(),
        "git_url": fake.url(),
        "env_vars": {},
        "domain": fake.domain_name(),
    }

    response = await authenticated_client.post("/applications", json=payload)
    assert response.status_code == 409


@pytest.mark.anyio
async def test_rename_application_to_unsluggable_name(
    authenticated_client: AsyncClient, application_create_test: Response
) -> None:
    application_id = application_create_test.json()["id"]

    response = await authenticated_client.patch(
        f"/applications/{application_id}", json={"name": "!!!"}
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_rename_application_regenerates_slug(
    authenticated_client: AsyncClient,
    application_create_test: Response,
    application_factory: Callable,
) -> None:
    application_id = application_create_test.json()["id"]

    response = await authenticated_client.patch(
        f"/applications/{application_id}", json={"name": "Deplocker Backend"}
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "deplocker-backend"

    # The old name and slug are free again.
    await application_factory(
        name="Deplocker API",
        description=fake.sentence(),
        git_url=fake.url(),
        env_vars={},
        domain=fake.domain_name(),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["Deplocker API", "deplocker-api"])
async def test_rename_application_to_taken_name(
    authenticated_client: AsyncClient,
    application_create_test: Response,
    application_factory: Callable,
    name: str,
) -> None:
    other_application = await application_factory(
        name="Other",
        description=fake.sentence(),
        git_url=fake.url(),
        env_vars={},
        domain=fake.domain_name(),
    )
    other_application_id = other_application.json()["id"]

    response = await authenticated_client.patch(
        f"/applications/{other_application_id}", json={"name": name}
    )
    assert response.status_code == 409

    response = await authenticated_client.get(f"/applications/{other_application_id}")
    assert response.json()["name"] == "Other"


@pytest.mark.anyio
@pytest.mark.parametrize(("method", "path"), APPLICATION_ROUTES)
@pytest.mark.parametrize("session_id", [None, "invalid-session"])
async def test_applications_require_authentication(
    client: AsyncClient, method: str, path: str, session_id: str | None
) -> None:
    if session_id is not None:
        client.cookies.set("session_id", session_id)

    response = await client.request(method, path)
    assert response.status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize(("method", "path"), APPLICATION_ROUTES)
async def test_applications_reject_expired_session(
    authenticated_client: AsyncClient, method: str, path: str
) -> None:
    # A session expires when Redis drops its key at the end of the TTL; deleting
    # the key reaches the same state without waiting for it.
    session_key = f"session:{authenticated_client.cookies['session_id']}"
    assert await redis.client.delete(session_key) == 1

    response = await authenticated_client.request(method, path)
    assert response.status_code == 401

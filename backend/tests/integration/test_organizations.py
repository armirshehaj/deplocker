"""An organization is created for, and listed to, the session's user alone. Its
name is a display label any organization may reuse; its slug is the
organization's handle, unique across all of them."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OrganizationMembersModel,
    OrganizationModel,
    ProjectModel,
    UserModel,
)
from app.schemas.organizations import OrganizationRole

ORGANIZATION_ROUTES = [
    ("POST", "/orgs/create"),
    ("GET", "/orgs"),
]


@pytest.fixture()
async def test_user_id(
    test_db_session: AsyncSession, default_organization_id: uuid.UUID
) -> int:
    owner_id = await test_db_session.scalar(
        select(OrganizationModel.owner_id).where(
            OrganizationModel.id == default_organization_id
        )
    )
    assert owner_id is not None
    return owner_id


@pytest.fixture()
async def squatted_default_slug(test_db_session: AsyncSession) -> OrganizationModel:
    """Another user's organization holding the name and slug the test user's
    default organization would get."""
    owner = UserModel(
        username="squatter",
        email="squatter@deplocker.com",
        full_name="Squatter",
        password="not-a-real-hash",
    )
    test_db_session.add(owner)
    await test_db_session.flush()

    organization = OrganizationModel(
        owner_id=owner.id,
        name="test_user's organization",
        slug="test-users-organization",
    )
    test_db_session.add(organization)
    await test_db_session.flush()

    return organization


@pytest.mark.anyio
@pytest.mark.parametrize(("method", "path"), ORGANIZATION_ROUTES)
@pytest.mark.parametrize("session_id", [None, "invalid-session"])
async def test_organizations_require_authentication(
    client: AsyncClient, method: str, path: str, session_id: str | None
) -> None:
    if session_id is not None:
        client.cookies.set("session_id", session_id)

    response = await client.request(method, path)
    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_organization_ignores_a_user_id_in_the_body(
    authenticated_client: AsyncClient,
    test_db_session: AsyncSession,
    test_user_id: int,
    foreign_project: ProjectModel,
) -> None:
    foreign_user_id = await test_db_session.scalar(
        select(OrganizationModel.owner_id).where(
            OrganizationModel.id == foreign_project.organization_id
        )
    )
    payload = {"user_id": foreign_user_id, "name": "Second organization"}

    response = await authenticated_client.post("/orgs/create", json=payload)
    assert response.status_code == 200
    assert response.json()["owner_id"] == test_user_id

    memberships = await test_db_session.scalars(
        select(OrganizationMembersModel).where(
            OrganizationMembersModel.organization_id == uuid.UUID(response.json()["id"])
        )
    )
    assert [(m.user_id, m.role) for m in memberships] == [
        (test_user_id, OrganizationRole.OWNER)
    ]


@pytest.mark.anyio
async def test_list_organizations_returns_only_the_callers(
    authenticated_client: AsyncClient,
    test_db_session: AsyncSession,
    default_organization_id: uuid.UUID,
    foreign_project: ProjectModel,
) -> None:
    created = await authenticated_client.post(
        "/orgs/create", json={"name": "Second organization"}
    )
    assert created.status_code == 200
    default_organization = await test_db_session.get(
        OrganizationModel, default_organization_id
    )
    assert default_organization is not None

    response = await authenticated_client.get("/orgs")
    assert response.status_code == 200
    # Both memberships are made in the test's one transaction, where now(), and
    # so joined_at, is the same for each: the order between them is undefined.
    assert sorted(response.json(), key=lambda org: org["slug"]) == sorted(
        [
            {
                "id": str(default_organization.id),
                "name": default_organization.name,
                "slug": default_organization.slug,
            },
            {
                "id": created.json()["id"],
                "name": "Second organization",
                "slug": "second-organization",
            },
        ],
        key=lambda org: org["slug"],
    )


@pytest.mark.anyio
async def test_create_organization_with_taken_slug(
    authenticated_client: AsyncClient, foreign_project: ProjectModel
) -> None:
    # "FOREIGN organization" is a different name, but gives the same slug as the
    # foreign project's organization.
    payload = {"name": "FOREIGN organization"}

    response = await authenticated_client.post("/orgs/create", json=payload)
    assert response.status_code == 409


@pytest.mark.anyio
async def test_create_organization_with_unsluggable_name(
    authenticated_client: AsyncClient,
) -> None:
    payload = {"name": "!!!"}

    response = await authenticated_client.post("/orgs/create", json=payload)
    assert response.status_code == 422


# `squatted_default_slug` comes first, so it exists before the test user
# registers.
@pytest.mark.anyio
async def test_default_organization_slug_is_suffixed_when_taken(
    squatted_default_slug: OrganizationModel,
    test_db_session: AsyncSession,
    default_organization_id: uuid.UUID,
) -> None:
    default_organization = await test_db_session.get(
        OrganizationModel, default_organization_id
    )
    assert default_organization is not None
    assert default_organization.name == squatted_default_slug.name
    assert default_organization.slug == "test-users-organization-2"

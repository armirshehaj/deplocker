import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DeploymentModel
from app.services.deployment import DeploymentService
from app.services.git import Commit


@pytest.mark.anyio
async def test_deployment_records_its_commit(
    authenticated_client: AsyncClient,
    application_create_test: Response,
    test_db_session: AsyncSession,
) -> None:
    create_response = await authenticated_client.post(
        "/deployments", json={"application_id": application_create_test.json()["id"]}
    )
    assert create_response.status_code == 201
    assert create_response.json()["commit_hash"] is None
    assert create_response.json()["commit_subject"] is None

    deployment_id = create_response.json()["id"]
    deployment = await test_db_session.get(DeploymentModel, uuid.UUID(deployment_id))
    assert deployment is not None

    commit = Commit(
        hash="9c1e4b7a2f8d3e6c5b0a9f8e7d6c5b4a3f2e1d0c",
        subject="Serve the API over HTTPS",
    )
    await DeploymentService(test_db_session).record_commit(deployment, commit)
    test_db_session.expire_all()

    response = await authenticated_client.get(f"/deployments/{deployment_id}")
    assert response.status_code == 200
    assert response.json()["commit_hash"] == commit.hash
    assert response.json()["commit_subject"] == commit.subject

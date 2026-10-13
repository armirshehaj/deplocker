import uuid

import pytest
from pydantic import ValidationError

from app.schemas.projects import ProjectCreate, ProjectUpdate


def test_project_create_valid() -> None:
    project_create_payload = {
        "name": "Deplocker",
        "description": "Dockerized deployments facility",
        "organization_id": str(uuid.uuid4()),
        "status": "active",
    }

    schema_object = ProjectCreate(**project_create_payload)

    assert schema_object.name == "Deplocker"
    assert schema_object.description == "Dockerized deployments facility"


def test_project_create_missing_description() -> None:
    payload = {"description": "Dockerized deployments facility"}

    with pytest.raises(ValidationError):
        ProjectCreate(**payload)


def test_project_create_missing_organization() -> None:
    payload = {"name": "Deplocker", "description": "Dockerized deployments facility"}

    with pytest.raises(ValidationError):
        ProjectCreate(**payload)


def test_project_partial_update() -> None:
    payload = {"name": "OpsDrift"}

    schema_object = ProjectUpdate(**payload)
    assert schema_object.name == "OpsDrift"
    assert schema_object.description is None

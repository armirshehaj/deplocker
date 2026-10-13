import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.applications import ApplicationCreate, ApplicationUpdate


@pytest.fixture()
def test_application_create_payload() -> dict[str, Any]:
    return {
        "name": "Deplocker API",
        "project_id": str(uuid.uuid4()),
        "description": "Deplocker Backend",
        "git_url": "https://github.com/armir-eng/deplocker-api.git",
        "env_vars": {"POSTGRES_USER": "postgres", "POSTGRES_HOST": "postgres"},
        "domain": "deplocker-api.armir.dev",
    }


def test_application_create_defaults(
    test_application_create_payload: dict[str, Any],
) -> None:
    schema_object = ApplicationCreate(**test_application_create_payload)

    assert schema_object.branch == "main"
    assert schema_object.dockerfile_path == "./Dockerfile"
    assert schema_object.port == 8000
    assert schema_object.desired_replicas == 1


def test_application_invalid_port(
    test_application_create_payload: dict[str, Any],
) -> None:
    test_application_create_payload["port"] = -8000
    with pytest.raises(ValidationError):
        ApplicationCreate(**test_application_create_payload)

    test_application_create_payload["port"] = "abc"
    with pytest.raises(ValidationError):
        ApplicationCreate(**test_application_create_payload)


def test_application_env_vars_dict(
    test_application_create_payload: dict[str, Any],
) -> None:
    schema_object = ApplicationCreate(**test_application_create_payload)
    assert schema_object.env_vars == test_application_create_payload["env_vars"]


def test_application_partial_update() -> None:
    payload = {
        "description": "Easily deploy and scale your dockerized projects",
        "git_url": "ssh://git@github.com/armir-eng/deplocker-api.git",
    }

    schema_object = ApplicationUpdate(**payload)

    for field, value in schema_object:
        if field == "description" or field == "git_url":
            assert value is not None

        else:
            assert value is None

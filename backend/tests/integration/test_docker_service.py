import docker
import pytest

from app.services.docker import DockerService


@pytest.mark.docker
@pytest.mark.anyio
async def test_daemon_version() -> None:
    expected = docker.from_env().version()["Version"]

    assert await DockerService().daemon_version() == expected

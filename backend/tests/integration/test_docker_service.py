import docker
import pytest

from app.services.docker import DockerService, NetworkNotFoundError


@pytest.mark.docker
@pytest.mark.anyio
async def test_daemon_version() -> None:
    expected = docker.from_env().version()["Version"]

    assert await DockerService().daemon_version() == expected


@pytest.mark.docker
@pytest.mark.anyio
async def test_network_of_the_deployed_applications() -> None:
    # DOCKER_NETWORK names the one the test stack declares
    await DockerService().ensure_network()


@pytest.mark.docker
@pytest.mark.anyio
async def test_missing_network() -> None:
    service = DockerService(network="deplocker-missing-net")

    with pytest.raises(NetworkNotFoundError, match="deplocker-missing-net"):
        await service.ensure_network()

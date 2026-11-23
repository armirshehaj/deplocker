import aiodocker
import pytest

from app.services.docker import DockerService, NetworkNotFoundError


@pytest.mark.docker
@pytest.mark.anyio
async def test_daemon_version(docker: aiodocker.Docker) -> None:
    expected = (await docker.version())["Version"]

    assert await DockerService(docker).daemon_version() == expected


@pytest.mark.docker
@pytest.mark.anyio
async def test_network_of_the_deployed_applications(docker: aiodocker.Docker) -> None:
    # DOCKER_NETWORK names the one the test stack declares
    await DockerService(docker).ensure_network()


@pytest.mark.docker
@pytest.mark.anyio
async def test_missing_network(docker: aiodocker.Docker) -> None:
    service = DockerService(docker, network="deplocker-missing-net")

    with pytest.raises(NetworkNotFoundError, match="deplocker-missing-net"):
        await service.ensure_network()

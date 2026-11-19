import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import docker
import httpx
import pytest
from docker.errors import ImageNotFound, NotFound

from app.core.conf import settings
from app.services.docker import (
    APPLICATION_LABEL,
    ContainerNameTakenError,
    DockerService,
    ImageNotFoundError,
    ResourceLimits,
)
from app.utils.docker.names import container_name

pytestmark = [pytest.mark.docker, pytest.mark.anyio]

# A web server answering on port 8000 with a page of its own
WEB_SERVER = """\
FROM busybox:1.36
RUN mkdir /www && echo hello from deplocker > /www/index.html
CMD ["httpd", "-f", "-p", "8000", "-h", "/www"]
"""

LIMITS = ResourceLimits(memory_mb=64, cpus=0.5)


@pytest.fixture
def application_id() -> Iterator[uuid.UUID]:
    """An application's id, whose container is removed after the test."""
    identifier = uuid.uuid4()
    yield identifier
    with contextlib.suppress(NotFound):
        docker.from_env().containers.get(container_name(identifier)).remove(force=True)


@pytest.fixture
async def web_server(tmp_path: Path) -> AsyncIterator[str]:
    """The tag of a web server's image, built for the test and removed after it."""
    (tmp_path / "Dockerfile").write_text(WEB_SERVER)
    tag = f"deplocker-test-web-{uuid.uuid4().hex[:12]}"
    await DockerService().build_image(tmp_path, tmp_path / "Dockerfile", tag)
    yield tag
    with contextlib.suppress(ImageNotFound):
        docker.from_env().images.remove(tag, force=True)


async def fetch(url: str) -> str:
    """The page at `url`, asked for again while the server starts up."""
    async with httpx.AsyncClient() as client:
        for _ in range(50):
            with contextlib.suppress(httpx.TransportError):
                return (await client.get(url)).text
            await asyncio.sleep(0.1)
    raise AssertionError(f"{url} never answered")


async def test_container_answers_by_name_on_the_network(
    application_id: uuid.UUID, web_server: str
) -> None:
    container = await DockerService().run_container(
        application_id, web_server, {}, LIMITS
    )

    assert container.name == container_name(application_id)
    assert await fetch(f"http://{container.name}:8000/") == "hello from deplocker\n"


async def test_container_is_reachable_on_the_network_alone(
    application_id: uuid.UUID, web_server: str
) -> None:
    container = await DockerService().run_container(
        application_id, web_server, {"GREETING": "hello"}, LIMITS
    )

    attributes = docker.from_env().containers.get(container.id).attrs
    assert not attributes["HostConfig"]["PortBindings"]
    assert not attributes["HostConfig"]["PublishAllPorts"]
    assert list(attributes["NetworkSettings"]["Networks"]) == [settings.DOCKER_NETWORK]
    assert "GREETING=hello" in attributes["Config"]["Env"]
    assert attributes["Config"]["Labels"][APPLICATION_LABEL] == str(application_id)


async def test_container_within_its_limits(
    application_id: uuid.UUID, web_server: str
) -> None:
    container = await DockerService().run_container(
        application_id, web_server, {}, LIMITS
    )

    host_config = docker.from_env().containers.get(container.id).attrs["HostConfig"]
    assert host_config["Memory"] == 64 * 1024 * 1024
    # No swap beyond the memory limit
    assert host_config["MemorySwap"] == host_config["Memory"]
    assert host_config["NanoCpus"] == 500_000_000


async def test_second_container_for_an_application(
    application_id: uuid.UUID, web_server: str
) -> None:
    service = DockerService()
    await service.run_container(application_id, web_server, {}, LIMITS)

    with pytest.raises(ContainerNameTakenError):
        await service.run_container(application_id, web_server, {}, LIMITS)


async def test_container_of_a_missing_image(application_id: uuid.UUID) -> None:
    with pytest.raises(ImageNotFoundError):
        await DockerService().run_container(
            application_id, "deplocker-test-missing:latest", {}, LIMITS
        )

    with pytest.raises(NotFound):
        docker.from_env().containers.get(container_name(application_id))

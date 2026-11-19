import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
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

# A process that exits on SIGTERM, and says when it listens for it
EXITS_ON_SIGTERM = """\
FROM busybox:1.36
CMD ["sh", "-c", "trap 'exit 0' TERM; echo ready; while true; do sleep 0.1; done"]
"""

# A process that ignores SIGTERM: a container's first process receives no signal
# it has no handler for
IGNORES_SIGTERM = """\
FROM busybox:1.36
CMD ["sleep", "300"]
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
async def build(tmp_path: Path) -> AsyncIterator[Callable[[str], Awaitable[str]]]:
    """Builds a Dockerfile, given as text, into an image for the test and returns
    the image's tag. The images are removed afterwards."""
    tags: list[str] = []

    async def build_image(dockerfile: str) -> str:
        context = tmp_path / f"context-{len(tags)}"
        context.mkdir()
        (context / "Dockerfile").write_text(dockerfile)
        tag = f"deplocker-test-{uuid.uuid4().hex[:12]}"
        await DockerService().build_image(context, context / "Dockerfile", tag)
        tags.append(tag)
        return tag

    yield build_image
    for tag in tags:
        with contextlib.suppress(ImageNotFound):
            docker.from_env().images.remove(tag, force=True)


@pytest.fixture
async def web_server(build: Callable[[str], Awaitable[str]]) -> str:
    """The tag of a web server's image."""
    return await build(WEB_SERVER)


def state_of(application_id: uuid.UUID) -> dict:
    """The state the daemon reports for an application's container."""
    container = docker.from_env().containers.get(container_name(application_id))
    return dict(container.attrs["State"])


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


async def test_stop_lets_the_container_exit_on_its_signal(
    application_id: uuid.UUID, build: Callable[[str], Awaitable[str]]
) -> None:
    service = DockerService(stop_timeout=10)
    await service.run_container(
        application_id, await build(EXITS_ON_SIGTERM), {}, LIMITS
    )
    container = docker.from_env().containers.get(container_name(application_id))
    for _ in range(50):
        if b"ready" in container.logs():
            break
        await asyncio.sleep(0.1)

    started = time.monotonic()
    assert await service.stop_container(application_id)

    assert time.monotonic() - started < 5
    assert state_of(application_id)["Status"] == "exited"
    assert state_of(application_id)["ExitCode"] == 0


async def test_stop_kills_a_container_past_its_grace_period(
    application_id: uuid.UUID, build: Callable[[str], Awaitable[str]]
) -> None:
    service = DockerService(stop_timeout=1)
    await service.run_container(
        application_id, await build(IGNORES_SIGTERM), {}, LIMITS
    )

    started = time.monotonic()
    assert await service.stop_container(application_id)

    assert time.monotonic() - started >= 1
    # 128 plus the number of SIGKILL
    assert state_of(application_id)["ExitCode"] == 137


async def test_remove_container(application_id: uuid.UUID, web_server: str) -> None:
    service = DockerService(stop_timeout=1)
    await service.run_container(application_id, web_server, {}, LIMITS)

    assert await service.remove_container(application_id)

    with pytest.raises(NotFound):
        docker.from_env().containers.get(container_name(application_id))


async def test_stop_and_remove_without_a_container(
    application_id: uuid.UUID,
) -> None:
    service = DockerService()

    assert not await service.stop_container(application_id)
    assert not await service.remove_container(application_id)

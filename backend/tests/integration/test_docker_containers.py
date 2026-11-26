import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any

import aiodocker
import httpx
import pytest

from app.core.conf import settings
from app.services.docker import (
    APPLICATION_LABEL,
    ContainerNameTakenError,
    ContainerState,
    ContainerStatus,
    DockerService,
    ImageNotFoundError,
    ResourceLimits,
)
from app.utils.docker.names import container_name

pytestmark = [pytest.mark.docker, pytest.mark.anyio]

# A web server answering on port 8000 with a page of its own, which says when it
# starts serving
WEB_SERVER = """\
FROM busybox:1.36
RUN mkdir /www && echo hello from deplocker > /www/index.html
CMD ["sh", "-c", "echo serving on port 8000; exec httpd -f -p 8000 -h /www"]
"""

# A process that exits on SIGTERM, and says when it listens for it
EXITS_ON_SIGTERM = """\
FROM busybox:1.36
CMD ["sh", "-c", "trap 'exit 0' TERM; echo ready; while true; do sleep 0.1; done"]
"""

# A process that writes 50 numbered lines, then waits
WRITES_LINES = """\
FROM busybox:1.36
CMD ["sh", "-c", "for i in $(seq 1 50); do echo line $i; done; sleep 300"]
"""

# A process that fails as soon as it starts
FAILS = """\
FROM busybox:1.36
CMD ["sh", "-c", "exit 3"]
"""

# A process that ignores SIGTERM: a container's first process receives no signal
# it has no handler for
IGNORES_SIGTERM = """\
FROM busybox:1.36
CMD ["sleep", "300"]
"""

LIMITS = ResourceLimits(memory_mb=64, cpus=0.5)


@pytest.fixture
async def application_id(docker: aiodocker.Docker) -> AsyncIterator[uuid.UUID]:
    """An application's id, whose container is removed after the test."""
    identifier = uuid.uuid4()
    yield identifier
    try:
        await docker.containers.container(container_name(identifier)).delete(force=True)
    except aiodocker.DockerError as error:
        if error.status != HTTPStatus.NOT_FOUND:
            raise


@pytest.fixture
async def build(
    docker: aiodocker.Docker, tmp_path: Path
) -> AsyncIterator[Callable[[str], Awaitable[str]]]:
    """Builds a Dockerfile, given as text, into an image for the test and returns
    the image's tag. The images are removed afterwards."""
    tags: list[str] = []

    async def build_image(dockerfile: str) -> str:
        context = tmp_path / f"context-{len(tags)}"
        context.mkdir()
        (context / "Dockerfile").write_text(dockerfile)
        tag = f"deplocker-test-{uuid.uuid4().hex[:12]}"
        await DockerService(docker).build_image(context, context / "Dockerfile", tag)
        tags.append(tag)
        return tag

    yield build_image
    for tag in tags:
        try:
            await docker.images.delete(tag, force=True)
        except aiodocker.DockerError as error:
            if error.status != HTTPStatus.NOT_FOUND:
                raise


@pytest.fixture
async def web_server(build: Callable[[str], Awaitable[str]]) -> str:
    """The tag of a web server's image."""
    return await build(WEB_SERVER)


async def inspect(docker: aiodocker.Docker, application_id: uuid.UUID) -> Any:
    """What the daemon reports of an application's container."""
    return await docker.containers.container(container_name(application_id)).show()


async def fetch(url: str) -> str:
    """The page at `url`, asked for again while the server starts up."""
    async with httpx.AsyncClient() as client:
        for _ in range(50):
            with contextlib.suppress(httpx.TransportError):
                return (await client.get(url)).text
            await asyncio.sleep(0.1)
    raise AssertionError(f"{url} never answered")


async def test_lifecycle_of_an_application_container(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    service = DockerService(docker, stop_timeout=1)

    container = await service.run_container(application_id, web_server, {}, LIMITS)
    status = await service.container_status(application_id)
    page = await fetch(f"http://{container.name}:8000/")
    tail = await service.container_logs(application_id, 10)
    removed = await service.remove_container(application_id)

    assert status.state is ContainerState.RUNNING
    assert page == "hello from deplocker\n"
    assert tail == ["serving on port 8000"]
    assert removed
    assert (
        await service.container_status(application_id)
    ).state is ContainerState.MISSING


async def test_container_answers_by_name_on_the_network(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    container = await DockerService(docker).run_container(
        application_id, web_server, {}, LIMITS
    )

    assert container.name == container_name(application_id)
    assert await fetch(f"http://{container.name}:8000/") == "hello from deplocker\n"


async def test_container_is_reachable_on_the_network_alone(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    container = await DockerService(docker).run_container(
        application_id, web_server, {"GREETING": "hello"}, LIMITS
    )

    attributes = await docker.containers.container(container.id).show()
    assert not attributes["HostConfig"]["PortBindings"]
    assert not attributes["HostConfig"]["PublishAllPorts"]
    assert list(attributes["NetworkSettings"]["Networks"]) == [settings.DOCKER_NETWORK]
    assert "GREETING=hello" in attributes["Config"]["Env"]
    assert attributes["Config"]["Labels"][APPLICATION_LABEL] == str(application_id)


async def test_container_within_its_limits(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    container = await DockerService(docker).run_container(
        application_id, web_server, {}, LIMITS
    )

    attributes = await docker.containers.container(container.id).show()
    host_config = attributes["HostConfig"]
    assert host_config["Memory"] == 64 * 1024 * 1024
    # No swap beyond the memory limit
    assert host_config["MemorySwap"] == host_config["Memory"]
    assert host_config["NanoCpus"] == 500_000_000


async def test_second_container_for_an_application(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    service = DockerService(docker)
    await service.run_container(application_id, web_server, {}, LIMITS)

    with pytest.raises(ContainerNameTakenError):
        await service.run_container(application_id, web_server, {}, LIMITS)


async def test_container_of_a_missing_image(
    docker: aiodocker.Docker, application_id: uuid.UUID
) -> None:
    with pytest.raises(ImageNotFoundError):
        await DockerService(docker).run_container(
            application_id, "deplocker-test-missing:latest", {}, LIMITS
        )

    with pytest.raises(aiodocker.DockerError, match="No such container"):
        await inspect(docker, application_id)


async def test_stop_lets_the_container_exit_on_its_signal(
    docker: aiodocker.Docker,
    application_id: uuid.UUID,
    build: Callable[[str], Awaitable[str]],
) -> None:
    service = DockerService(docker, stop_timeout=10)
    await service.run_container(
        application_id, await build(EXITS_ON_SIGTERM), {}, LIMITS
    )
    container = docker.containers.container(container_name(application_id))
    for _ in range(50):
        if "ready" in "".join(await container.log(stdout=True)):
            break
        await asyncio.sleep(0.1)

    started = time.monotonic()
    assert await service.stop_container(application_id)

    assert time.monotonic() - started < 5
    state = (await inspect(docker, application_id))["State"]
    assert state["Status"] == "exited"
    assert state["ExitCode"] == 0


async def test_stop_kills_a_container_past_its_grace_period(
    docker: aiodocker.Docker,
    application_id: uuid.UUID,
    build: Callable[[str], Awaitable[str]],
) -> None:
    service = DockerService(docker, stop_timeout=1)
    await service.run_container(
        application_id, await build(IGNORES_SIGTERM), {}, LIMITS
    )

    started = time.monotonic()
    assert await service.stop_container(application_id)

    assert time.monotonic() - started >= 1
    # 128 plus the number of SIGKILL
    assert (await inspect(docker, application_id))["State"]["ExitCode"] == 137


async def test_remove_container(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    service = DockerService(docker, stop_timeout=1)
    await service.run_container(application_id, web_server, {}, LIMITS)

    assert await service.remove_container(application_id)

    with pytest.raises(aiodocker.DockerError, match="No such container"):
        await inspect(docker, application_id)


async def test_stop_and_remove_without_a_container(
    docker: aiodocker.Docker,
    application_id: uuid.UUID,
) -> None:
    service = DockerService(docker)

    assert not await service.stop_container(application_id)
    assert not await service.remove_container(application_id)


async def test_status_of_a_running_container(
    docker: aiodocker.Docker, application_id: uuid.UUID, web_server: str
) -> None:
    service = DockerService(docker)
    await service.run_container(application_id, web_server, {}, LIMITS)

    assert await service.container_status(application_id) == ContainerStatus(
        ContainerState.RUNNING
    )


async def test_status_of_a_stopped_container(
    docker: aiodocker.Docker,
    application_id: uuid.UUID,
    build: Callable[[str], Awaitable[str]],
) -> None:
    service = DockerService(docker, stop_timeout=0)
    await service.run_container(
        application_id, await build(IGNORES_SIGTERM), {}, LIMITS
    )
    await service.stop_container(application_id)

    assert await service.container_status(application_id) == ContainerStatus(
        ContainerState.STOPPED, exit_code=137
    )


async def test_status_of_a_crashing_container(
    docker: aiodocker.Docker,
    application_id: uuid.UUID,
    build: Callable[[str], Awaitable[str]],
) -> None:
    service = DockerService(docker)
    await service.run_container(application_id, await build(FAILS), {}, LIMITS)

    for _ in range(100):
        status = await service.container_status(application_id)
        if status.state is ContainerState.RESTARTING:
            break
        await asyncio.sleep(0.1)

    assert status.state is ContainerState.RESTARTING
    assert status.exit_code == 3


async def test_status_without_a_container(
    docker: aiodocker.Docker, application_id: uuid.UUID
) -> None:
    assert await DockerService(docker).container_status(
        application_id
    ) == ContainerStatus(ContainerState.MISSING)


async def test_log_tail(
    docker: aiodocker.Docker,
    application_id: uuid.UUID,
    build: Callable[[str], Awaitable[str]],
) -> None:
    service = DockerService(docker)
    await service.run_container(application_id, await build(WRITES_LINES), {}, LIMITS)

    for _ in range(50):
        tail = await service.container_logs(application_id, 5)
        if tail and tail[-1] == "line 50":
            break
        await asyncio.sleep(0.1)

    assert tail == [f"line {number}" for number in range(46, 51)]


async def test_log_tail_without_a_container(
    docker: aiodocker.Docker, application_id: uuid.UUID
) -> None:
    assert await DockerService(docker).container_logs(application_id, 5) is None

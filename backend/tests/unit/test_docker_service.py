import asyncio
import uuid

import pytest

from app.core.docker import docker_client
from app.services.docker import DockerService, DockerUnavailableError


@pytest.mark.anyio
@pytest.mark.usefixtures("unreachable_daemon")
async def test_daemon_out_of_reach_on_connecting() -> None:
    with pytest.raises(DockerUnavailableError, match="Docker daemon is unreachable"):
        async with docker_client() as client:
            await DockerService(client).daemon_version()


@pytest.mark.anyio
@pytest.mark.usefixtures("vanishing_daemon")
async def test_daemon_lost_during_a_call() -> None:
    with pytest.raises(DockerUnavailableError, match="Docker daemon is unreachable"):
        async with docker_client() as client:
            await DockerService(client).daemon_version()


@pytest.mark.anyio
@pytest.mark.usefixtures("silent_daemon")
async def test_daemon_that_never_answers() -> None:
    with pytest.raises(DockerUnavailableError, match=r"no answer within 0\.5s"):
        async with docker_client() as client:
            await DockerService(client, daemon_timeout=0.5).daemon_version()


@pytest.mark.anyio
@pytest.mark.usefixtures("silent_daemon")
async def test_stop_waits_out_its_grace_period() -> None:
    application_id = uuid.uuid4()

    with pytest.raises(DockerUnavailableError, match=r"no answer within 1\.5s"):
        async with docker_client() as client:
            service = DockerService(client, stop_timeout=1, daemon_timeout=0.5)
            await service.stop_container(application_id)


@pytest.mark.anyio
async def test_output_lines_of_any_length() -> None:
    # Longer than the 64 KiB StreamReader.readline accepts
    long_line = "x" * 200_000
    stream = asyncio.StreamReader()
    stream.feed_data(f"first\r\n{long_line}\nlast".encode())
    stream.feed_eof()

    lines = [line async for line in DockerService._lines(stream)]

    assert lines == ["first", long_line, "last"]

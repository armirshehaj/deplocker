import asyncio

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
async def test_output_lines_of_any_length() -> None:
    # Longer than the 64 KiB StreamReader.readline accepts
    long_line = "x" * 200_000
    stream = asyncio.StreamReader()
    stream.feed_data(f"first\r\n{long_line}\nlast".encode())
    stream.feed_eof()

    lines = [line async for line in DockerService._lines(stream)]

    assert lines == ["first", long_line, "last"]

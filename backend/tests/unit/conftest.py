import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest


@pytest.fixture
def unreachable_daemon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Points the Docker client at a socket no daemon listens on."""
    monkeypatch.setenv("DOCKER_HOST", f"unix://{tmp_path}/docker.sock")


@pytest.fixture
async def vanishing_daemon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[None]:
    """Points the Docker client at a socket whose daemon starts every answer and
    hangs up before finishing it."""

    async def answer_partly(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await reader.readuntil(b"\r\n\r\n")
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 100\r\n"
            b"\r\n"
            b'{"Version":'
        )
        await writer.drain()
        writer.close()

    socket = tmp_path / "docker.sock"
    server = await asyncio.start_unix_server(answer_partly, path=socket)
    monkeypatch.setenv("DOCKER_HOST", f"unix://{socket}")
    async with server:
        yield

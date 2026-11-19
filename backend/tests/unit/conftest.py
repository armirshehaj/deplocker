from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.docker import get_docker_client


@pytest.fixture
def unreachable_daemon(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Points docker-py at a socket no daemon listens on."""
    monkeypatch.setenv("DOCKER_HOST", f"unix://{tmp_path}/docker.sock")
    get_docker_client.cache_clear()
    yield
    get_docker_client.cache_clear()

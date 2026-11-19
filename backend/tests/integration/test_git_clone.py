import subprocess
from pathlib import Path

import pytest

from app.services.git import GitService

# A small public repository whose history has stayed the same for years
REPOSITORY_URL = "https://github.com/octocat/Hello-World"


@pytest.mark.network
@pytest.mark.anyio
async def test_clone_of_a_public_repository(tmp_path: Path) -> None:
    service = GitService()

    clone = await service.clone_repository(REPOSITORY_URL, "master", tmp_path / "clone")
    commit = await service.read_head_commit(clone)

    head = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert commit.hash == head

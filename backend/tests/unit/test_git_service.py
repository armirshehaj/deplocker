import os
import subprocess
from pathlib import Path

import pytest

from app.services.git import (
    BranchNotFoundError,
    GitService,
    RepositoryNotFoundError,
)

# Isolates the fixture repositories from the git configuration of the machine
# running the tests
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Test User",
    "GIT_AUTHOR_EMAIL": "test.user@deplocker.com",
    "GIT_COMMITTER_NAME": "Test User",
    "GIT_COMMITTER_EMAIL": "test.user@deplocker.com",
}


def git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        env=GIT_ENV,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture()
def repository(tmp_path: Path) -> Path:
    """A repository on `main` whose commit message has a subject and a body."""
    path = tmp_path / "repository"
    path.mkdir()
    git(path, "init", "--quiet", "--initial-branch=main")
    git(
        path,
        "commit",
        "--quiet",
        "--allow-empty",
        "--message=Serve the API over HTTPS",
        "--message=Caddy terminates TLS in front of it.",
    )
    return path


@pytest.mark.anyio
async def test_clone_repository(repository: Path, tmp_path: Path) -> None:
    git(repository, "commit", "--quiet", "--allow-empty", "--message=Add a healthcheck")
    destination = tmp_path / "clone"

    clone = await GitService(allowed_protocols=("file",)).clone_repository(
        f"file://{repository}", "main", destination
    )

    assert clone == destination
    assert git(clone, "rev-parse", "HEAD") == git(repository, "rev-parse", "HEAD")
    assert git(clone, "rev-list", "--count", "HEAD") == "1"


@pytest.mark.anyio
async def test_clone_repository_checks_out_the_requested_branch(
    repository: Path, tmp_path: Path
) -> None:
    git(repository, "switch", "--quiet", "--create", "staging")
    git(repository, "commit", "--quiet", "--allow-empty", "--message=Stage a release")
    git(repository, "switch", "--quiet", "main")

    clone = await GitService(allowed_protocols=("file",)).clone_repository(
        f"file://{repository}", "staging", tmp_path / "clone"
    )

    assert git(clone, "rev-parse", "HEAD") == git(repository, "rev-parse", "staging")


@pytest.mark.anyio
async def test_clone_repository_of_a_missing_branch(
    repository: Path, tmp_path: Path
) -> None:
    with pytest.raises(BranchNotFoundError):
        await GitService(allowed_protocols=("file",)).clone_repository(
            f"file://{repository}", "release", tmp_path / "clone"
        )


@pytest.mark.anyio
async def test_clone_repository_of_a_missing_repository(tmp_path: Path) -> None:
    with pytest.raises(RepositoryNotFoundError):
        await GitService(allowed_protocols=("file",)).clone_repository(
            f"file://{tmp_path / 'missing'}", "main", tmp_path / "clone"
        )


@pytest.mark.anyio
async def test_clone_repository_over_a_protocol_not_allowed(
    repository: Path, tmp_path: Path
) -> None:
    with pytest.raises(RepositoryNotFoundError):
        await GitService().clone_repository(
            f"file://{repository}", "main", tmp_path / "clone"
        )

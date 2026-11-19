import asyncio
import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.services.git import (
    BranchNotFoundError,
    CloneTimeoutError,
    DockerfileNotFoundError,
    DockerfileOutsideRepositoryError,
    GitError,
    GitService,
    RepositoryNotFoundError,
    RepositoryTooLargeError,
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


@pytest.mark.anyio
async def test_clone_repository_larger_than_allowed(
    repository: Path, tmp_path: Path
) -> None:
    (repository / "assets.bin").write_bytes(os.urandom(2_000_000))
    git(repository, "add", "assets.bin")
    git(repository, "commit", "--quiet", "--message=Add the assets")
    service = GitService(allowed_protocols=("file",), max_repository_size_mb=1)

    with pytest.raises(RepositoryTooLargeError):
        await service.clone_repository(
            f"file://{repository}", "main", tmp_path / "clone"
        )


@pytest.mark.anyio
async def test_clone_repository_whose_files_outgrow_the_download(
    repository: Path, tmp_path: Path
) -> None:
    # Zeros compress to almost nothing, so the download stays small
    (repository / "zeros.bin").write_bytes(bytes(5_000_000))
    git(repository, "add", "zeros.bin")
    git(repository, "commit", "--quiet", "--message=Add the zeros")
    service = GitService(allowed_protocols=("file",), max_repository_size_mb=1)
    destination = tmp_path / "clone"

    with pytest.raises(RepositoryTooLargeError):
        await service.clone_repository(f"file://{repository}", "main", destination)

    assert not (destination / "zeros.bin").exists()


@pytest.mark.anyio
async def test_clone_repository_aborts_a_download_that_outgrows_the_limit(
    tmp_path: Path,
) -> None:
    aborted = asyncio.Event()

    async def download() -> None:
        (tmp_path / "pack").write_bytes(bytes(2_000_000))
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            aborted.set()
            raise

    with pytest.raises(RepositoryTooLargeError):
        await GitService(max_repository_size_mb=1)._watching_size(tmp_path, download())

    assert aborted.is_set()


@pytest.fixture()
async def silent_server() -> AsyncIterator[str]:
    """The URL of a repository whose server accepts connections and never
    answers them."""

    async def ignore(reader: asyncio.StreamReader, _: asyncio.StreamWriter) -> None:
        await reader.read()

    server = await asyncio.start_server(ignore, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}/repository.git"
    server.close()
    # Times out while a git process that outlived the clone holds a connection
    async with asyncio.timeout(5):
        await server.wait_closed()


@pytest.mark.anyio
async def test_clone_repository_taking_longer_than_allowed(
    silent_server: str, tmp_path: Path
) -> None:
    service = GitService(allowed_protocols=("http",), clone_timeout=0.5)

    with pytest.raises(CloneTimeoutError):
        await service.clone_repository(silent_server, "main", tmp_path / "clone")


@pytest.mark.anyio
async def test_read_head_commit(repository: Path) -> None:
    commit = await GitService().read_head_commit(repository)

    assert commit.hash == git(repository, "rev-parse", "HEAD")
    assert commit.subject == "Serve the API over HTTPS"


@pytest.mark.anyio
async def test_read_head_commit_of_a_shallow_clone(
    repository: Path, tmp_path: Path
) -> None:
    git(repository, "commit", "--quiet", "--allow-empty", "--message=Add a healthcheck")
    service = GitService(allowed_protocols=("file",))

    clone = await service.clone_repository(
        f"file://{repository}", "main", tmp_path / "clone"
    )
    commit = await service.read_head_commit(clone)

    assert commit.hash == git(repository, "rev-parse", "HEAD")
    assert commit.subject == "Add a healthcheck"


@pytest.mark.anyio
async def test_read_head_commit_beside_a_file_named_head(repository: Path) -> None:
    (repository / "HEAD").write_text("A tenant's file, not a revision\n")
    git(repository, "add", "HEAD")
    git(repository, "commit", "--quiet", "--message=Add a file named HEAD")

    commit = await GitService().read_head_commit(repository)

    assert commit.subject == "Add a file named HEAD"


@pytest.mark.anyio
async def test_read_head_commit_with_an_empty_message(repository: Path) -> None:
    git(
        repository,
        "commit",
        "--quiet",
        "--allow-empty",
        "--allow-empty-message",
        "--message=",
    )

    commit = await GitService().read_head_commit(repository)

    assert commit.hash == git(repository, "rev-parse", "HEAD")
    assert commit.subject == ""


@pytest.mark.anyio
async def test_read_head_commit_outside_a_repository(tmp_path: Path) -> None:
    with pytest.raises(GitError):
        await GitService().read_head_commit(tmp_path)


@pytest.mark.parametrize(
    ("dockerfile_path", "expected"),
    [
        ("./Dockerfile", "Dockerfile"),
        ("Dockerfile", "Dockerfile"),
        ("docker/api.Dockerfile", "docker/api.Dockerfile"),
        ("docker/../Dockerfile", "Dockerfile"),
    ],
)
def test_resolve_dockerfile(
    repository: Path, dockerfile_path: str, expected: str
) -> None:
    (repository / "Dockerfile").write_text("FROM scratch\n")
    (repository / "docker").mkdir()
    (repository / "docker" / "api.Dockerfile").write_text("FROM scratch\n")

    dockerfile = GitService().resolve_dockerfile(repository, dockerfile_path)

    assert dockerfile == (repository / expected).resolve()


def test_resolve_dockerfile_through_a_link_inside_the_repository(
    repository: Path,
) -> None:
    (repository / "docker").mkdir()
    (repository / "docker" / "api.Dockerfile").write_text("FROM scratch\n")
    (repository / "Dockerfile").symlink_to("docker/api.Dockerfile")

    dockerfile = GitService().resolve_dockerfile(repository, "Dockerfile")

    assert dockerfile == (repository / "docker" / "api.Dockerfile").resolve()


@pytest.mark.parametrize(
    "dockerfile_path", ["Dockerfile", "docker/Dockerfile", "docker"]
)
def test_resolve_dockerfile_missing(repository: Path, dockerfile_path: str) -> None:
    (repository / "docker").mkdir()

    with pytest.raises(DockerfileNotFoundError):
        GitService().resolve_dockerfile(repository, dockerfile_path)


@pytest.fixture()
def outside_dockerfile(tmp_path: Path) -> Path:
    """A Dockerfile beside the repository, which no path may reach."""
    path = tmp_path / "Dockerfile"
    path.write_text("FROM scratch\n")
    return path


@pytest.mark.parametrize(
    "dockerfile_path", ["../Dockerfile", "docker/../../Dockerfile"]
)
@pytest.mark.usefixtures("outside_dockerfile")
def test_resolve_dockerfile_through_parent_directories(
    repository: Path, dockerfile_path: str
) -> None:
    (repository / "docker").mkdir()

    with pytest.raises(DockerfileOutsideRepositoryError):
        GitService().resolve_dockerfile(repository, dockerfile_path)


def test_resolve_dockerfile_at_an_absolute_path(
    repository: Path, outside_dockerfile: Path
) -> None:
    with pytest.raises(DockerfileOutsideRepositoryError):
        GitService().resolve_dockerfile(repository, str(outside_dockerfile))


def test_resolve_dockerfile_through_a_link_to_a_file_outside(
    repository: Path, outside_dockerfile: Path
) -> None:
    (repository / "Dockerfile").symlink_to(outside_dockerfile)

    with pytest.raises(DockerfileOutsideRepositoryError):
        GitService().resolve_dockerfile(repository, "Dockerfile")


def test_resolve_dockerfile_through_a_link_to_a_directory_outside(
    repository: Path, outside_dockerfile: Path
) -> None:
    (repository / "docker").symlink_to(outside_dockerfile.parent)

    with pytest.raises(DockerfileOutsideRepositoryError):
        GitService().resolve_dockerfile(repository, "docker/Dockerfile")

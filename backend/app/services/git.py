import asyncio
import contextlib
import os
import signal
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.core.conf import settings
from app.utils.git.urls import carries_credentials


class GitError(Exception):
    """A repository could not be made into a working tree to build from."""


class RepositoryNotFoundError(GitError):
    """The URL does not lead to a repository git can read."""


class BranchNotFoundError(GitError):
    """The repository has no branch of the requested name."""


class DockerfileNotFoundError(GitError):
    """The repository has no file at the Dockerfile path."""


class DockerfileOutsideRepositoryError(GitError):
    """The Dockerfile path leads out of the repository."""


class CredentialsInUrlError(GitError):
    """The URL holds credentials, which the platform never takes in a URL."""


class CloneTimeoutError(GitError):
    """The clone took longer than it is allowed."""


class RepositoryTooLargeError(GitError):
    """The repository fills more space than it is allowed."""


# How often, in seconds, a download's size on disk is checked against the limit
SIZE_CHECK_INTERVAL = 0.5


@dataclass(frozen=True)
class Commit:
    """The commit a working tree is checked out at."""

    hash: str
    subject: str


class GitService:
    def __init__(
        self,
        allowed_protocols: Sequence[str] = ("https",),
        clone_timeout: float = settings.GIT_CLONE_TIMEOUT_SECONDS,
        max_repository_size_mb: float = settings.GIT_MAX_REPOSITORY_SIZE_MB,
    ) -> None:
        self.clone_timeout = clone_timeout
        self.max_repository_size_mb = max_repository_size_mb
        self.env = {
            **os.environ,
            # Keeps a tenant's URL from reaching repositories on the server's disk
            "GIT_ALLOW_PROTOCOL": ":".join(allowed_protocols),
            # Keeps the server's git configuration, credential helpers included,
            # out of a tenant's clone
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            # Fails a repository that asks for credentials instead of waiting
            "GIT_TERMINAL_PROMPT": "0",
        }

    async def clone_repository(
        self, url: str, branch: str, destination: Path, depth: int = 1
    ) -> Path:
        if carries_credentials(url):
            raise CredentialsInUrlError("Repository URL must not carry credentials")
        try:
            async with asyncio.timeout(self.clone_timeout):
                await self._clone(url, branch, destination, depth)
        except TimeoutError as error:
            raise CloneTimeoutError(
                f"Clone took longer than {self.clone_timeout:g}s"
            ) from error
        return destination

    async def _clone(
        self, url: str, branch: str, destination: Path, depth: int
    ) -> None:
        # Under --exit-code, ls-remote exits with 2 when no branch matches
        returncode, _, stderr = await self._git(
            "ls-remote", "--exit-code", "--", url, f"refs/heads/{branch}"
        )
        if returncode == 2:
            raise BranchNotFoundError(f"Branch '{branch}' not found in the repository")
        if returncode != 0:
            raise RepositoryNotFoundError(
                f"Repository not found or not accessible: {stderr}"
            )

        # The files are written only once their size is known to fit: content
        # that compresses well makes them far larger than the download
        returncode, _, stderr = await self._watching_size(
            destination,
            self._git(
                "clone",
                "--quiet",
                "--no-checkout",
                "--depth",
                str(depth),
                "--branch",
                branch,
                "--",
                url,
                str(destination),
            ),
        )
        if returncode != 0:
            raise GitError(f"Clone failed: {stderr}")

        returncode, stdout, stderr = await self._git(
            "-C", str(destination), "ls-tree", "-r", "--format=%(objectsize)", "HEAD"
        )
        if returncode != 0:
            raise GitError(f"Reading the size of the files failed: {stderr}")
        # A submodule, which is not cloned, has no size
        files_size = sum(int(size) for size in stdout.split() if size != "-")
        history_size = await asyncio.to_thread(self._size_on_disk, destination)
        self._check_size(history_size + files_size)

        returncode, _, stderr = await self._git(
            "-C", str(destination), "checkout", "--quiet"
        )
        if returncode != 0:
            raise GitError(f"Checkout failed: {stderr}")

    async def _watching_size[T](self, directory: Path, operation: Awaitable[T]) -> T:
        """The result of `operation`, which is cancelled if `directory` grows past
        the size limit while it runs."""
        task = asyncio.ensure_future(operation)
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=SIZE_CHECK_INTERVAL)
                self._check_size(await asyncio.to_thread(self._size_on_disk, directory))
            return task.result()
        finally:
            task.cancel()
            await asyncio.wait({task})

    def _check_size(self, size: int) -> None:
        if size > self.max_repository_size_mb * 1_000_000:
            raise RepositoryTooLargeError(
                f"Repository is larger than {self.max_repository_size_mb:g} MB"
            )

    @staticmethod
    def _size_on_disk(directory: Path) -> int:
        size = 0
        for root, _, files in directory.walk():
            for name in files:
                # git renames and removes its temporary files as it goes
                with contextlib.suppress(FileNotFoundError):
                    size += (root / name).lstat().st_size
        return size

    async def read_head_commit(self, repository: Path) -> Commit:
        returncode, stdout, stderr = await self._git(
            "-C", str(repository), "log", "-1", "--format=%H%x00%s"
        )
        if returncode != 0:
            raise GitError(f"Reading the commit failed: {stderr}")
        commit_hash, subject = stdout.split("\0", 1)
        return Commit(hash=commit_hash, subject=subject)

    def resolve_dockerfile(self, repository: Path, dockerfile_path: str) -> Path:
        """The Dockerfile at `dockerfile_path`, which a tenant gives relative to
        the repository's root. A path that leads out of the repository, through
        `..`, an absolute path or a symbolic link, is refused."""
        root = repository.resolve()
        dockerfile = (root / dockerfile_path).resolve()
        if not dockerfile.is_relative_to(root):
            raise DockerfileOutsideRepositoryError(
                f"Dockerfile '{dockerfile_path}' is outside the repository"
            )
        if not dockerfile.is_file():
            raise DockerfileNotFoundError(
                f"Dockerfile '{dockerfile_path}' not found in the repository"
            )
        return dockerfile

    async def _git(self, *args: str) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
            # A process group of its own, so that a cancelled command's helpers,
            # such as the one that downloads over HTTPS, stop along with it
            start_new_session=True,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            raise
        return (
            await process.wait(),
            stdout.decode(errors="replace").strip(),
            stderr.decode(errors="replace").strip(),
        )

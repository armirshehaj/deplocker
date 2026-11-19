import asyncio
import contextlib
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class GitError(Exception):
    """A git operation on a repository failed."""


class RepositoryNotFoundError(GitError):
    """The URL does not lead to a repository git can read."""


class BranchNotFoundError(GitError):
    """The repository has no branch of the requested name."""


@dataclass(frozen=True)
class Commit:
    """The commit a working tree is checked out at."""

    hash: str
    subject: str


class GitService:
    def __init__(self, allowed_protocols: Sequence[str] = ("https",)) -> None:
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

        returncode, _, stderr = await self._git(
            "clone",
            "--quiet",
            "--depth",
            str(depth),
            "--branch",
            branch,
            "--",
            url,
            str(destination),
        )
        if returncode != 0:
            raise GitError(f"Clone failed: {stderr}")
        return destination

    async def read_head_commit(self, repository: Path) -> Commit:
        returncode, stdout, stderr = await self._git(
            "-C", str(repository), "log", "-1", "--format=%H%x00%s"
        )
        if returncode != 0:
            raise GitError(f"Reading the commit failed: {stderr}")
        commit_hash, subject = stdout.split("\0", 1)
        return Commit(hash=commit_hash, subject=subject)

    async def _git(self, *args: str) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise
        return (
            await process.wait(),
            stdout.decode(errors="replace").strip(),
            stderr.decode(errors="replace").strip(),
        )

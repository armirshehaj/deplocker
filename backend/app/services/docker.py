import asyncio
import contextlib
import os
import signal
import tempfile
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from docker import DockerClient
from docker.errors import DockerException, NotFound
from requests.exceptions import ConnectionError as DaemonConnectionError

from app.core.conf import settings
from app.core.docker import DOCKER_HOST, get_docker_client

# How many of a build's last lines of output its error carries
BUILD_OUTPUT_TAIL_LINES = 20


class DockerError(Exception):
    """The Docker daemon could not carry out an operation."""


class DockerUnavailableError(DockerError):
    """The Docker daemon cannot be reached."""

    def __init__(self, reason: Exception) -> None:
        super().__init__(f"Docker daemon is unreachable at {DOCKER_HOST}: {reason}")


class NetworkNotFoundError(DockerError):
    """The network the deployed applications join does not exist."""


class BuildError(DockerError):
    """An image could not be built from its Dockerfile."""

    def __init__(self, message: str, output_tail: Sequence[str]) -> None:
        super().__init__(message)
        self.output_tail = list(output_tail)


class BuildTimeoutError(BuildError):
    """The build took longer than it is allowed."""


@dataclass(frozen=True)
class Image:
    """An image the daemon holds."""

    tag: str
    id: str


class DockerService:
    """Builds images and runs containers on the host's Docker daemon."""

    def __init__(
        self,
        network: str = settings.DOCKER_NETWORK,
        build_timeout: float = settings.DOCKER_BUILD_TIMEOUT_SECONDS,
    ) -> None:
        self.network = network
        self.build_timeout = build_timeout

    async def daemon_version(self) -> str:
        """The version of the daemon the platform builds and runs on."""
        version = await self._call(lambda client: client.version())
        return str(version["Version"])

    async def ensure_network(self) -> None:
        """Checks that the network the deployed applications join exists. Raises
        NetworkNotFoundError when it does not."""
        try:
            await self._call(lambda client: client.networks.get(self.network))
        except NotFound as error:
            raise NetworkNotFoundError(
                f"Docker network {self.network} does not exist; "
                "`docker compose up` creates it"
            ) from error

    async def build_image(
        self,
        context: Path,
        dockerfile: Path,
        tag: str,
        on_output: Callable[[str], Awaitable[None]] | None = None,
    ) -> Image:
        """Builds `dockerfile` with BuildKit, on the files under `context`, into an
        image tagged `tag`. Each line of the build's output goes to `on_output` as
        it arrives.

        Raises BuildError when the build fails, and BuildTimeoutError when it
        outlasts `build_timeout`; both carry the build's last lines of output."""
        tail: deque[str] = deque(maxlen=BUILD_OUTPUT_TAIL_LINES)
        with tempfile.TemporaryDirectory(prefix="deplocker-build-") as scratch:
            id_file = Path(scratch) / "image-id"
            try:
                async with asyncio.timeout(self.build_timeout):
                    status = await self._build(
                        [
                            "--file",
                            str(dockerfile),
                            "--tag",
                            tag,
                            "--iidfile",
                            str(id_file),
                            str(context),
                        ],
                        tail,
                        on_output,
                    )
            except TimeoutError as error:
                raise BuildTimeoutError(
                    f"Build took longer than {self.build_timeout:g}s", tail
                ) from error
            if status != 0:
                raise BuildError(f"Build failed with exit status {status}", tail)
            return Image(tag=tag, id=id_file.read_text().strip())

    async def _build(
        self,
        arguments: list[str],
        tail: deque[str],
        on_output: Callable[[str], Awaitable[None]] | None,
    ) -> int:
        """Runs `docker buildx build`, passing each line of its output to `tail`
        and `on_output`, and returns its exit status. The build stops, with every
        process it started, when the caller is cancelled or `on_output` fails."""
        process = await asyncio.create_subprocess_exec(
            "docker",
            "buildx",
            "build",
            "--progress=plain",
            "--load",
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            # A process group of its own, so that the buildx plugin the command
            # starts stops along with it; the daemon cancels a build whose client
            # is gone
            start_new_session=True,
        )
        assert process.stdout is not None
        try:
            async for line in self._lines(process.stdout):
                tail.append(line)
                if on_output is not None:
                    await on_output(line)
            return await process.wait()
        except BaseException:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            raise

    @staticmethod
    async def _lines(stream: asyncio.StreamReader) -> AsyncIterator[str]:
        """The lines `stream` carries, decoded and without their line breaks, at
        any length: StreamReader.readline fails on a line over 64 KiB."""
        pending = b""
        while chunk := await stream.read(2**16):
            *lines, pending = (pending + chunk).split(b"\n")
            for line in lines:
                yield line.rstrip(b"\r").decode(errors="replace")
        if pending:
            yield pending.rstrip(b"\r").decode(errors="replace")

    async def _call[T](self, operation: Callable[[DockerClient], T]) -> T:
        """Runs `operation` on the shared client in a worker thread, since docker-py
        blocks for the whole of each call. Raises DockerUnavailableError when the
        daemon cannot be reached, on connecting or during the call."""

        def run() -> T:
            try:
                client = get_docker_client()
            except DockerException as error:
                raise DockerUnavailableError(error) from error
            try:
                return operation(client)
            except DaemonConnectionError as error:
                raise DockerUnavailableError(error) from error

        return await asyncio.to_thread(run)

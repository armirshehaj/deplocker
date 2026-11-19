import asyncio
import contextlib
import os
import signal
import tempfile
import uuid
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from docker import DockerClient
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from requests.exceptions import ConnectionError as DaemonConnectionError

from app.core.conf import settings
from app.core.docker import DOCKER_HOST, get_docker_client
from app.utils.docker.names import container_name

# How many of a build's last lines of output its error carries
BUILD_OUTPUT_TAIL_LINES = 20

# Marks each container the platform runs with the application it serves
APPLICATION_LABEL = "deplocker.application"

# The most lines of a container's output a log tail returns
LOG_TAIL_MAX_LINES = 1000


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


class ImageNotFoundError(DockerError):
    """The daemon holds no image of the given name."""


class ContainerNameTakenError(DockerError):
    """The application already has a container."""


@dataclass(frozen=True)
class Image:
    """An image the daemon holds."""

    tag: str
    id: str


@dataclass(frozen=True)
class ResourceLimits:
    """The resources a container may use: memory in MB, and a number of the
    host's CPUs."""

    memory_mb: int
    cpus: float


@dataclass(frozen=True)
class Container:
    """A container the daemon runs."""

    id: str
    name: str


class ContainerState(Enum):
    """Where an application's container stands."""

    RUNNING = "running"
    # Exited, and about to start again under its restart policy
    RESTARTING = "restarting"
    STOPPED = "stopped"
    MISSING = "missing"


# The platform's reading of each state Docker reports for a container
DOCKER_STATES = {
    "created": ContainerState.STOPPED,
    "running": ContainerState.RUNNING,
    "paused": ContainerState.STOPPED,
    "restarting": ContainerState.RESTARTING,
    "removing": ContainerState.STOPPED,
    "exited": ContainerState.STOPPED,
    "dead": ContainerState.STOPPED,
}


@dataclass(frozen=True)
class ContainerStatus:
    """An application's container as the daemon reports it: its state, the exit
    code of its last run once that run has ended, and how many times its
    restart policy has started it again."""

    state: ContainerState
    exit_code: int | None = None
    restart_count: int = 0


class DockerService:
    """Builds images and runs containers on the host's Docker daemon."""

    def __init__(
        self,
        network: str = settings.DOCKER_NETWORK,
        build_timeout: float = settings.DOCKER_BUILD_TIMEOUT_SECONDS,
        stop_timeout: int = settings.DOCKER_STOP_TIMEOUT_SECONDS,
    ) -> None:
        self.network = network
        self.build_timeout = build_timeout
        self.stop_timeout = stop_timeout

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

    async def run_container(
        self,
        application_id: uuid.UUID,
        image: str,
        environment: Mapping[str, str],
        limits: ResourceLimits,
    ) -> Container:
        """Starts an application's container from `image`, with `environment` as its
        environment variables, using no more than `limits`. It joins the deployed
        applications' network under the application's container name and
        publishes no port on the host, so it is reachable on that network alone.

        Raises ImageNotFoundError when the daemon holds no `image`, and
        ContainerNameTakenError when the application already has a container."""
        name = container_name(application_id)

        def run(client: DockerClient) -> Any:
            # Created, then started: containers.run would pull an image it cannot
            # find, from a registry that never holds the platform's images
            container = client.containers.create(
                image,
                name=name,
                environment=dict(environment),
                network=self.network,
                labels={APPLICATION_LABEL: str(application_id)},
                # Back after a crash or a restart of the daemon, unless stopped
                restart_policy={"Name": "unless-stopped"},
                mem_limit=f"{limits.memory_mb}m",
                # The same as the memory limit, so no swap is added beyond it
                memswap_limit=f"{limits.memory_mb}m",
                nano_cpus=round(limits.cpus * 1_000_000_000),
            )
            try:
                container.start()
            except BaseException:
                container.remove(force=True)
                raise
            return container

        try:
            container = await self._call(run)
        except ImageNotFound as error:
            raise ImageNotFoundError(f"Image {image} does not exist") from error
        except APIError as error:
            if error.status_code == 409:
                raise ContainerNameTakenError(
                    f"Container {name} already exists"
                ) from error
            raise
        return Container(id=str(container.id), name=name)

    async def stop_container(self, application_id: uuid.UUID) -> bool:
        """Stops an application's container: it receives its stop signal, SIGTERM
        unless its image names another, and is killed if it has not exited
        `stop_timeout` seconds later. Returns whether the application had a
        container."""

        def stop(client: DockerClient) -> None:
            client.containers.get(container_name(application_id)).stop(
                timeout=self.stop_timeout
            )

        return await self._on_container(stop)

    async def remove_container(self, application_id: uuid.UUID) -> bool:
        """Stops an application's container as `stop_container` does, then removes
        it. Returns whether the application had a container; one already gone is
        not an error."""

        def remove(client: DockerClient) -> None:
            container = client.containers.get(container_name(application_id))
            container.stop(timeout=self.stop_timeout)
            container.remove()

        return await self._on_container(remove)

    async def container_status(self, application_id: uuid.UUID) -> ContainerStatus:
        """The status of an application's container, whose state is MISSING when
        the application has none."""

        def inspect(client: DockerClient) -> Any:
            try:
                return client.containers.get(container_name(application_id)).attrs
            except NotFound:
                return None

        attributes = await self._call(inspect)
        if attributes is None:
            return ContainerStatus(ContainerState.MISSING)
        state = DOCKER_STATES[attributes["State"]["Status"]]
        return ContainerStatus(
            state=state,
            exit_code=(
                None
                if state is ContainerState.RUNNING
                else int(attributes["State"]["ExitCode"])
            ),
            restart_count=int(attributes["RestartCount"]),
        )

    async def container_logs(
        self, application_id: uuid.UUID, lines: int
    ) -> list[str] | None:
        """The last `lines` lines, `LOG_TAIL_MAX_LINES` at most, that an
        application's container wrote to its output and error streams. None when
        the application has no container."""

        def read(client: DockerClient) -> Any:
            try:
                container = client.containers.get(container_name(application_id))
            except NotFound:
                return None
            return container.logs(tail=max(1, min(lines, LOG_TAIL_MAX_LINES)))

        output = await self._call(read)
        if output is None:
            return None
        text: str = output.decode(errors="replace")
        return text.splitlines()

    async def _on_container(self, operation: Callable[[DockerClient], None]) -> bool:
        """Runs `operation` on an application's container, and returns whether the
        container existed: absent when the operation starts, or gone before it
        ends."""
        try:
            await self._call(operation)
        except NotFound:
            return False
        return True

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

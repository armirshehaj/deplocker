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
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import aiodocker
import aiohttp
from aiodocker.containers import DockerContainer

from app.core.conf import settings
from app.utils.docker.names import container_name

if TYPE_CHECKING:
    from aiodocker.types import JSONObject

# How many of a build's last lines of output its error carries
BUILD_OUTPUT_TAIL_LINES = 20

# Marks each container the platform runs with the application it serves
APPLICATION_LABEL = "deplocker.application"

# The most lines of a container's output a log tail returns
LOG_TAIL_MAX_LINES = 1000

# The status of aiodocker's error for a daemon it cannot connect to
UNREACHABLE_STATUS = 900


class DockerError(Exception):
    """The Docker daemon could not carry out an operation."""


class DockerUnavailableError(DockerError):
    """The Docker daemon cannot be reached."""

    def __init__(self, reason: object) -> None:
        super().__init__(f"Docker daemon is unreachable: {reason}")


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
    """Builds images and runs containers on the host's Docker daemon, which
    `client` reaches."""

    def __init__(
        self,
        client: aiodocker.Docker,
        network: str = settings.DOCKER_NETWORK,
        build_timeout: float = settings.DOCKER_BUILD_TIMEOUT_SECONDS,
        stop_timeout: int = settings.DOCKER_STOP_TIMEOUT_SECONDS,
    ) -> None:
        self.client = client
        self.network = network
        self.build_timeout = build_timeout
        self.stop_timeout = stop_timeout

    async def daemon_version(self) -> str:
        """The version of the daemon the platform builds and runs on."""
        version = await self._call(self.client.version())
        return str(version["Version"])

    async def ensure_network(self) -> None:
        """Checks that the network the deployed applications join exists. Raises
        NetworkNotFoundError when it does not."""
        try:
            await self._call(self.client.networks.get(self.network))
        except aiodocker.DockerError as error:
            if error.status != HTTPStatus.NOT_FOUND:
                raise
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
        memory = limits.memory_mb * 1024 * 1024
        config: JSONObject = {
            "Image": image,
            "Env": [f"{variable}={value}" for variable, value in environment.items()],
            "Labels": {APPLICATION_LABEL: str(application_id)},
            "HostConfig": {
                "NetworkMode": self.network,
                # Back after a crash or a restart of the daemon, unless stopped
                "RestartPolicy": {"Name": "unless-stopped"},
                "Memory": memory,
                # The same as the memory limit, so no swap is added beyond it
                "MemorySwap": memory,
                "NanoCpus": round(limits.cpus * 1_000_000_000),
            },
        }

        async def run() -> DockerContainer:
            # Created, then started: containers.run would pull an image it cannot
            # find, from a registry that never holds the platform's images
            container = await self.client.containers.create(config, name=name)
            try:
                await container.start()
            except BaseException:
                await container.delete(force=True)
                raise
            return container

        try:
            container = await self._call(run())
        except aiodocker.DockerError as error:
            if error.status == HTTPStatus.NOT_FOUND:
                raise ImageNotFoundError(f"Image {image} does not exist") from error
            if error.status == HTTPStatus.CONFLICT:
                raise ContainerNameTakenError(
                    f"Container {name} already exists"
                ) from error
            raise
        return Container(id=container.id, name=name)

    async def stop_container(self, application_id: uuid.UUID) -> bool:
        """Stops an application's container: it receives its stop signal, SIGTERM
        unless its image names another, and is killed if it has not exited
        `stop_timeout` seconds later. Returns whether the application had a
        container."""
        container = self._container(application_id)
        return await self._on_container(container.stop(t=self.stop_timeout))

    async def remove_container(self, application_id: uuid.UUID) -> bool:
        """Stops an application's container as `stop_container` does, then removes
        it. Returns whether the application had a container; one already gone is
        not an error."""
        container = self._container(application_id)

        async def remove() -> None:
            await container.stop(t=self.stop_timeout)
            await container.delete()

        return await self._on_container(remove())

    async def container_status(self, application_id: uuid.UUID) -> ContainerStatus:
        """The status of an application's container, whose state is MISSING when
        the application has none."""
        try:
            attributes = await self._call(self._container(application_id).show())
        except aiodocker.DockerError as error:
            if error.status != HTTPStatus.NOT_FOUND:
                raise
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
        read = self._container(application_id).log(
            stdout=True, stderr=True, tail=max(1, min(lines, LOG_TAIL_MAX_LINES))
        )
        try:
            output = await self._call(read)
        except aiodocker.DockerError as error:
            if error.status != HTTPStatus.NOT_FOUND:
                raise
            return None
        return "".join(output).splitlines()

    def _container(self, application_id: uuid.UUID) -> DockerContainer:
        """An application's container, addressed by its name, which the daemon
        looks up on each call."""
        return self.client.containers.container(container_name(application_id))

    async def _on_container(self, operation: Awaitable[None]) -> bool:
        """Awaits `operation` on an application's container, and returns whether
        the container existed: absent when the operation starts, or gone before
        it ends."""
        try:
            await self._call(operation)
        except aiodocker.DockerError as error:
            if error.status != HTTPStatus.NOT_FOUND:
                raise
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

    @staticmethod
    async def _call[T](operation: Awaitable[T]) -> T:
        """Awaits `operation` on the daemon. Raises DockerUnavailableError when the
        daemon cannot be reached, on connecting or during the call."""
        try:
            return await operation
        except aiodocker.DockerError as error:
            if error.status == UNREACHABLE_STATUS:
                raise DockerUnavailableError(error.message) from error
            raise
        except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError) as error:
            raise DockerUnavailableError(error) from error

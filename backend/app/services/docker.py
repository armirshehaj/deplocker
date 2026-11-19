import asyncio
from collections.abc import Callable

from docker import DockerClient
from docker.errors import DockerException, NotFound
from requests.exceptions import ConnectionError as DaemonConnectionError

from app.core.conf import settings
from app.core.docker import DOCKER_HOST, get_docker_client


class DockerError(Exception):
    """The Docker daemon could not carry out an operation."""


class DockerUnavailableError(DockerError):
    """The Docker daemon cannot be reached."""

    def __init__(self, reason: Exception) -> None:
        super().__init__(f"Docker daemon is unreachable at {DOCKER_HOST}: {reason}")


class NetworkNotFoundError(DockerError):
    """The network the deployed applications join does not exist."""


class DockerService:
    """Builds images and runs containers on the host's Docker daemon."""

    def __init__(self, network: str = settings.DOCKER_NETWORK) -> None:
        self.network = network

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

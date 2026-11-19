import pytest
from requests.exceptions import ConnectionError as DaemonConnectionError

from app.services.docker import DockerService, DockerUnavailableError


class LostDaemonClient:
    """A client whose daemon went away after it connected."""

    def version(self) -> dict[str, str]:
        raise DaemonConnectionError("Connection aborted.")


@pytest.mark.anyio
@pytest.mark.usefixtures("unreachable_daemon")
async def test_daemon_out_of_reach_on_connecting() -> None:
    with pytest.raises(DockerUnavailableError, match="Docker daemon is unreachable"):
        await DockerService().daemon_version()


@pytest.mark.anyio
async def test_daemon_lost_during_a_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.docker.get_docker_client", lambda: LostDaemonClient()
    )

    with pytest.raises(DockerUnavailableError, match="Connection aborted"):
        await DockerService().daemon_version()

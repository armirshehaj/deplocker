import os

import aiodocker


def docker_client() -> aiodocker.Docker:
    """A client of the host's Docker daemon: the one at DOCKER_HOST, else at the
    socket docker-compose.yml mounts from the host, as for the Docker command line
    that runs builds. It holds connections on the event loop it is used on until
    it is closed, as `async with docker_client()` does."""
    return aiodocker.Docker(
        url=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
    )

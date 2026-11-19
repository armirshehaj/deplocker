import functools
import os

import docker

# Where docker-py and the Docker command line find the daemon: DOCKER_HOST, or
# the socket docker-compose.yml mounts from the host
DOCKER_HOST = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")


@functools.cache
def get_docker_client() -> docker.DockerClient:
    """The client every operation on the host's Docker daemon shares, connected on
    first use. Raises DockerException when the daemon is out of reach; the next
    call tries again."""
    return docker.from_env()

import asyncio
import contextlib
import re
import uuid
from collections.abc import AsyncIterator
from http import HTTPStatus
from pathlib import Path

import aiodocker
import pytest
from httpx import AsyncClient

from app.services.docker import BuildError, BuildTimeoutError, DockerService

pytestmark = [pytest.mark.docker, pytest.mark.anyio]


@pytest.fixture
async def tag(docker: aiodocker.Docker) -> AsyncIterator[str]:
    """A name no other image holds; echoed by a build step, it also keeps the
    build cache from replaying that step. The image is removed afterwards."""
    name = f"deplocker-test-build-{uuid.uuid4().hex[:12]}"
    yield name
    try:
        await docker.images.delete(name, force=True)
    except aiodocker.DockerError as error:
        if error.status != HTTPStatus.NOT_FOUND:
            raise


def build_context(directory: Path, *instructions: str) -> Path:
    """`directory`, holding a Dockerfile that runs `instructions` on busybox."""
    lines = ["FROM busybox:1.36", *instructions]
    (directory / "Dockerfile").write_text("\n".join(lines) + "\n")
    return directory


def is_step_output(line: str, text: str) -> bool:
    """Whether `line` is a build step printing `text`, as BuildKit's plain
    progress shows it: the step's number, the time into the step, the text."""
    return re.fullmatch(rf"#\d+ \d+\.\d+ {re.escape(text)}", line) is not None


def docker_processes() -> list[str]:
    """The Docker command line's processes alive in this container."""
    names = []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        with contextlib.suppress(OSError):
            # "<pid> (<name>) <state> …"; a zombie's state is Z
            head, _, rest = stat.read_text().rpartition(")")
            name, state = head.partition("(")[2], rest.split()[0]
            if name.startswith("docker") and state != "Z":
                names.append(name)
    return names


async def test_build_with_buildkit_features(
    docker: aiodocker.Docker, tmp_path: Path, tag: str
) -> None:
    context = build_context(
        tmp_path, f"RUN --mount=type=cache,target=/cache echo {tag}"
    )
    output: list[str] = []

    async def collect(line: str) -> None:
        output.append(line)

    image = await DockerService(docker).build_image(
        context, context / "Dockerfile", tag, collect
    )

    assert any(is_step_output(line, tag) for line in output)
    assert image.id == (await docker.images.inspect(tag))["Id"]


async def test_failed_build(docker: aiodocker.Docker, tmp_path: Path, tag: str) -> None:
    context = build_context(tmp_path, f"RUN echo {tag} && exit 3")

    with pytest.raises(BuildError) as raised:
        await DockerService(docker).build_image(context, context / "Dockerfile", tag)

    assert any("exit code: 3" in line for line in raised.value.output_tail)


async def test_build_timeout(
    docker: aiodocker.Docker, tmp_path: Path, tag: str
) -> None:
    context = build_context(tmp_path, f"RUN echo {tag} && sleep 60")

    with pytest.raises(BuildTimeoutError, match="longer than 3s"):
        await DockerService(docker, build_timeout=3).build_image(
            context, context / "Dockerfile", tag
        )

    assert docker_processes() == []


async def test_api_answers_while_an_image_builds(
    client: AsyncClient, docker: aiodocker.Docker, tmp_path: Path, tag: str
) -> None:
    context = build_context(tmp_path, f"RUN echo {tag} && sleep 5")
    step_started = asyncio.Event()

    async def watch(line: str) -> None:
        if is_step_output(line, tag):
            step_started.set()

    build = asyncio.create_task(
        DockerService(docker).build_image(context, context / "Dockerfile", tag, watch)
    )
    await asyncio.wait_for(step_started.wait(), timeout=60)

    response = await client.get("/health")

    assert response.status_code == 200
    assert not build.done()
    await build

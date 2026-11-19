import time
import uuid
from pathlib import Path
from typing import Annotated

import typer

from app.core.conf import settings
from app.services.docker import DockerError, DockerService
from app.utils.cli.commands import async_command
from app.utils.docker.names import image_tag as tag_for

app = typer.Typer(help="Run the Docker service's operations.", no_args_is_help=True)


@app.command()
@async_command
async def version() -> None:
    """Connect to the Docker daemon as the API does on startup, and show its
    version."""
    try:
        daemon_version = await DockerService().daemon_version()
    except DockerError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Daemon      {daemon_version}")


@app.command()
@async_command
async def network(
    name: Annotated[
        str, typer.Argument(help="The network the deployed applications join.")
    ] = settings.DOCKER_NETWORK,
) -> None:
    """Check that the network the deployed applications join exists, as the API
    does on startup."""
    try:
        await DockerService(network=name).ensure_network()
    except DockerError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Network     {name}")


@app.command()
@async_command
async def build(
    context: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            resolve_path=True,
            help="The directory whose files the build works on.",
        ),
    ],
    tag: Annotated[str, typer.Option("--tag", "-t", help="The image's name.")],
    dockerfile: Annotated[
        Path | None,
        typer.Option(
            "--file",
            "-f",
            resolve_path=True,
            help="The Dockerfile. Without it, the one at the context's root.",
        ),
    ] = None,
    timeout: Annotated[
        float, typer.Option(min=0, help="Abort the build after this many seconds.")
    ] = settings.DOCKER_BUILD_TIMEOUT_SECONDS,
) -> None:
    """Build an image with BuildKit as the platform does, showing the build's
    output as it arrives."""

    async def show(line: str) -> None:
        typer.echo(line)

    started = time.perf_counter()
    try:
        image = await DockerService(build_timeout=timeout).build_image(
            context, dockerfile or context / "Dockerfile", tag, on_output=show
        )
    except DockerError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error
    elapsed = time.perf_counter() - started

    typer.echo()
    typer.echo(f"Image       {image.tag}")
    typer.echo(f"ID          {image.id}")
    typer.echo(f"Took        {elapsed:.1f}s")


@app.command()
def image_tag(
    application_id: Annotated[uuid.UUID, typer.Argument(help="The application's id.")],
    commit_hash: Annotated[str, typer.Argument(help="The commit's full hash.")],
) -> None:
    """Show the tag the platform gives the image an application builds from a
    commit."""
    try:
        tag = tag_for(application_id, commit_hash)
    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error

    typer.echo(tag)

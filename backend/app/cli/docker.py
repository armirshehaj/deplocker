from typing import Annotated

import typer

from app.core.conf import settings
from app.services.docker import DockerError, DockerService
from app.utils.cli.commands import async_command

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

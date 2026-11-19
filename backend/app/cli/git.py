import time
from pathlib import Path
from typing import Annotated

import typer

from app.services.git import GitError, GitService
from app.utils.cli.commands import async_command
from app.utils.deployments.workspace import deployment_workspace

app = typer.Typer(help="Run the Git service's operations.", no_args_is_help=True)


@app.command()
@async_command
async def clone(
    url: Annotated[str, typer.Argument(help="The repository's URL.")],
    branch: Annotated[
        str, typer.Option("--branch", "-b", help="The branch to check out.")
    ] = "main",
    depth: Annotated[
        int, typer.Option(min=1, help="How many of the latest commits to fetch.")
    ] = 1,
    dockerfile_path: Annotated[
        str | None,
        typer.Option(
            "--dockerfile",
            help="Also find the Dockerfile at this path, relative to the "
            "repository's root, as a deployment does before it builds.",
        ),
    ] = None,
    into: Annotated[
        Path | None,
        typer.Option(
            resolve_path=True,
            help="Keep the clone in this directory, which must be empty or not "
            "exist yet. Without it, the clone is deleted afterwards.",
        ),
    ] = None,
) -> None:
    """Clone a branch of a repository as the platform does, and show the commit it
    checked out."""
    service = GitService()
    async with deployment_workspace() as workspace:
        destination = into or workspace / "repository"
        started = time.perf_counter()
        try:
            repository = await service.clone_repository(url, branch, destination, depth)
            commit = await service.read_head_commit(repository)
            dockerfile = (
                service.resolve_dockerfile(repository, dockerfile_path)
                .relative_to(repository.resolve())
                .as_posix()
                if dockerfile_path is not None
                else None
            )
        except GitError as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from error
        elapsed = time.perf_counter() - started

    typer.echo(f"Commit      {commit.hash}")
    typer.echo(f"Subject     {commit.subject}")
    if dockerfile is not None:
        typer.echo(f"Dockerfile  {dockerfile}")
    typer.echo(f"Took        {elapsed:.1f}s")
    if into:
        typer.echo(f"Kept in     {into}")

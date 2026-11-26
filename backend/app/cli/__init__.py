import typer

from app.cli import docker, git

app = typer.Typer(
    help="Run the platform's operations by hand, on real input.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="markdown",
)
app.add_typer(docker.app, name="docker")
app.add_typer(git.app, name="git")

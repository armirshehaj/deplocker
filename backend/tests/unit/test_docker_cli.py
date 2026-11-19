import pytest
from typer.testing import CliRunner

from app.cli import app


@pytest.mark.usefixtures("unreachable_daemon")
@pytest.mark.parametrize("command", [["version"], ["network"]])
def test_command_without_a_daemon(command: list[str]) -> None:
    result = CliRunner().invoke(app, ["docker", *command])

    assert result.exit_code == 1
    assert "Docker daemon is unreachable" in result.stderr

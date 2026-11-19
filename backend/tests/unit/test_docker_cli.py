import pytest
from typer.testing import CliRunner

from app.cli import app


@pytest.mark.usefixtures("unreachable_daemon")
def test_version_without_a_daemon() -> None:
    result = CliRunner().invoke(app, ["docker", "version"])

    assert result.exit_code == 1
    assert "Docker daemon is unreachable" in result.stderr

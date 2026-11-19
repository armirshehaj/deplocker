from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app


@pytest.mark.usefixtures("unreachable_daemon")
@pytest.mark.parametrize("command", [["version"], ["network"]])
def test_command_without_a_daemon(command: list[str]) -> None:
    result = CliRunner().invoke(app, ["docker", *command])

    assert result.exit_code == 1
    assert "Docker daemon is unreachable" in result.stderr


@pytest.mark.usefixtures("unreachable_daemon")
def test_build_without_a_daemon(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM busybox:1.36\n")

    result = CliRunner().invoke(
        app, ["docker", "build", str(tmp_path), "--tag", "deplocker-unbuilt"]
    )

    assert result.exit_code == 1
    assert "Build failed" in result.stderr

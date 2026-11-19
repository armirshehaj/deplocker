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


def test_image_tag() -> None:
    application_id = "0b3e9c4e-5f1a-4c2b-9d7e-8a6f5b4c3d2e"
    commit_hash = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"

    result = CliRunner().invoke(
        app, ["docker", "image-tag", application_id, commit_hash]
    )

    assert result.exit_code == 0
    assert result.stdout == f"deplocker-app-{application_id}:{commit_hash}\n"


def test_image_tag_of_a_branch_name() -> None:
    result = CliRunner().invoke(
        app, ["docker", "image-tag", "0b3e9c4e-5f1a-4c2b-9d7e-8a6f5b4c3d2e", "main"]
    )

    assert result.exit_code == 1
    assert "Not a full commit hash" in result.stderr

from pathlib import Path

from typer.testing import CliRunner

from app.cli import app


def test_clone_of_a_repository_out_of_reach(tmp_path: Path) -> None:
    # The platform clones over HTTPS only
    result = CliRunner().invoke(app, ["git", "clone", f"file://{tmp_path}"])

    assert result.exit_code == 1
    assert "Repository not found or not accessible" in result.stderr

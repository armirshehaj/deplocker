import asyncio
import tempfile
from pathlib import Path

import pytest

from app.utils.deployments.workspace import deployment_workspace


@pytest.fixture()
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The directory workspaces are created in, so a test sees any left behind."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


@pytest.mark.anyio
async def test_deployment_workspace(temp_root: Path) -> None:
    async with deployment_workspace() as workspace:
        assert workspace.parent == temp_root
        (workspace / "repository").mkdir()
        (workspace / "repository" / "Dockerfile").write_text("FROM scratch\n")

    assert list(temp_root.iterdir()) == []


@pytest.mark.anyio
async def test_deployment_workspace_when_the_deployment_fails(
    temp_root: Path,
) -> None:
    with pytest.raises(RuntimeError):
        async with deployment_workspace() as workspace:
            (workspace / "Dockerfile").write_text("FROM scratch\n")
            raise RuntimeError("The build failed")

    assert list(temp_root.iterdir()) == []


@pytest.mark.anyio
async def test_deployment_workspace_when_the_deployment_is_cancelled(
    temp_root: Path,
) -> None:
    entered = asyncio.Event()

    async def deploy() -> None:
        async with deployment_workspace() as workspace:
            (workspace / "Dockerfile").write_text("FROM scratch\n")
            entered.set()
            await asyncio.Event().wait()

    deployment = asyncio.create_task(deploy())
    await entered.wait()
    deployment.cancel()
    with pytest.raises(asyncio.CancelledError):
        await deployment

    assert list(temp_root.iterdir()) == []

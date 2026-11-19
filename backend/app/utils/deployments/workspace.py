import asyncio
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path


@asynccontextmanager
async def deployment_workspace() -> AsyncIterator[Path]:
    """A new directory for one deployment's files, its clone among them, removed
    on exit whether the deployment succeeds, fails or is cancelled."""
    path = Path(tempfile.mkdtemp(prefix="deplocker-"))
    try:
        yield path
    finally:
        # Off the event loop: removing a large clone takes a while
        await asyncio.to_thread(shutil.rmtree, path)

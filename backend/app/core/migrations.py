from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _database_heads(connection: Connection) -> set[str]:
    return set(MigrationContext.configure(connection).get_current_heads())


async def ensure_schema_is_current(engine: AsyncEngine) -> None:
    """
    Refuses to start the app unless the database is at the migration head
    """
    expected = set(ScriptDirectory.from_config(Config(ALEMBIC_INI)).get_heads())

    async with engine.connect() as conn:
        current = await conn.run_sync(_database_heads)

    if current != expected:
        raise RuntimeError(
            f"Database schema is at {sorted(current) or 'no revision'}, "
            f"but the code expects {sorted(expected)}. "
            "Run `alembic upgrade head` before starting the app."
        )

import re
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import settings
from app.core.database import (
    DATABASE_URL,
    Base,
    get_db_session,
)
from app.main import app

TEST_DB_URL = re.sub(r"\/(?!.*\/).*", f"/{settings.TEST_DB}", DATABASE_URL)
test_engine = create_async_engine(TEST_DB_URL)
# Bound to a connection already inside the per-test transaction, a session's
# rollback would end that transaction by default; with savepoints, a route that
# rolls back only undoes its own work.
test_session = async_sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
    join_transaction_mode="create_savepoint",
)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a transactional session that rolls back at the end of each test
    """
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = test_session(bind=conn)
        yield session

        await session.close()
        await transaction.rollback()


@pytest.fixture
async def client(test_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client that uses the test database"""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8080"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

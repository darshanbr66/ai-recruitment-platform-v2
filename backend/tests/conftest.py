from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.core.asyncio_compat import configure_event_loop_policy

configure_event_loop_policy()

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def db_connection() -> AsyncGenerator[AsyncConnection, None]:
    """One connection + one outer transaction per test, rolled back at the
    end regardless of what the test does — including code under test that
    calls `session.commit()` (join_transaction_mode="create_savepoint" turns
    that into a savepoint release instead of an actual commit). Keeps tests
    from needing a separate database or leaving data behind.
    """
    async with engine.connect() as connection:
        await connection.begin()
        yield connection
        await connection.rollback()


@pytest_asyncio.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

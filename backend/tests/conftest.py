from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.core.asyncio_compat import configure_event_loop_policy

configure_event_loop_policy()

from app.core.security import hash_password  # noqa: E402
from app.db.rls import rls_bypass  # noqa: E402
from app.db.session import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.rbac import Role, UserRole  # noqa: E402
from app.models.user import User  # noqa: E402

# Fixed test credentials for the one platform account that can't be created
# through the HTTP API (see app/cli.py) — seeded directly here the same way
# the CLI does it, so tests can log in as a real SUPER_ADMIN.
SUPER_ADMIN_EMAIL = "super.admin@platform.dev"
SUPER_ADMIN_PASSWORD = "SuperSecretPass1"


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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An HTTP client against the real app, with `get_db` overridden to use
    this test's rolled-back transaction instead of a fresh production
    session — so hitting real endpoints (register, login, etc.) never
    writes to the live database. Mirrors the real `get_db`'s
    commit/rollback-on-exception so a request that fails mid-write (e.g. a
    duplicate-email 409) doesn't leave the shared test transaction aborted
    for the rest of the test.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def super_admin(db_session: AsyncSession) -> User:
    """Seeds a platform SUPER_ADMIN directly, mirroring `app/cli.py` — there
    is no HTTP path that can create one (that's the point; see
    app/cli.py's module docstring). Email/password are the module-level
    `SUPER_ADMIN_EMAIL`/`SUPER_ADMIN_PASSWORD` constants above.
    """
    async with rls_bypass(db_session):
        role = await db_session.scalar(
            select(Role).where(Role.organization_id.is_(None), Role.name == "SUPER_ADMIN")
        )
        assert role is not None, "SUPER_ADMIN system role must be seeded by migrations"

        user = User(
            organization_id=None,
            email=SUPER_ADMIN_EMAIL,
            hashed_password=hash_password(SUPER_ADMIN_PASSWORD),
            full_name="Platform Admin",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(UserRole(user_id=user.id, role_id=role.id))
        await db_session.flush()

    return user


async def login(client: AsyncClient, *, email: str, password: str) -> dict:
    """Logs in via the real endpoint and returns the parsed JSON body.
    `httpx.AsyncClient` persists cookies across calls on the same instance,
    so the refresh-token cookie this sets is automatically sent by any
    later `client.post("/api/v1/recruiter/auth/refresh", ...)` in the same
    test — no manual cookie plumbing needed.
    """
    response = await client.post(
        "/api/v1/recruiter/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped session.

    The auth dependencies (`app/api/deps.py`) layer on top of this to call
    `rls.set_tenant_context()`/`rls.set_rls_bypass()` with the authenticated
    principal's organization_id before any query runs. `SET LOCAL`-based
    session variables live for exactly this one transaction, so commit here
    — once, at the very end of the request — rather than scattering
    `db.commit()` calls through services.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

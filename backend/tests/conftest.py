"""
Test harness for AutoPilot backend.

SETUP REQUIRED (run once against the test database):

    createdb autopilot_test
    DATABASE_URL=postgresql+psycopg://autopilot:autopilot@localhost:5432/autopilot_test \\
        alembic upgrade head

CONFIGURE via environment variables before running (or let the defaults below
handle a standard local Docker Compose setup):

    DATABASE_URL      — full async URL for the test Postgres DB
    SECRET_KEY        — any string (tests use their own)
    POSTGRES_PASSWORD — required by Settings even when DATABASE_URL is set
    SEED_ADMIN_PASSWORD / SEED_ADMIN_EMAIL — used to seed the test admin user

ISOLATION STRATEGY:
    Each test function receives a rolled-back AsyncSession.  Service code that
    calls session.commit() creates/releases a SAVEPOINT rather than a real
    commit (join_transaction_mode="create_savepoint"), so changes are visible
    within the test but disappear on teardown.  Seed data (admin user and
    invoice_processing workflow) is created inside each test's session and
    therefore also rolls back automatically.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

# ── Set required env vars BEFORE any app module is imported ──────────────────
# pydantic-settings reads env vars when Settings() is first instantiated
# (via @lru_cache on get_settings).  Values already set in the environment
# take precedence; these defaults cover a typical local dev setup.
os.environ.setdefault("POSTGRES_PASSWORD", "autopilot")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "AdminPass123!")
os.environ.setdefault("SEED_ADMIN_EMAIL", "admin@autopilot.dev")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://autopilot:autopilot@localhost:5432/autopilot_test",
)
# ─────────────────────────────────────────────────────────────────────────────

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.workflow import Workflow

_settings = get_settings()

# ── Test engine ───────────────────────────────────────────────────────────────
# Separate from the app's module-level engine.  Points to the same (test) URL
# so no schema divergence is possible.
_test_engine = create_async_engine(
    _settings.resolved_database_url,
    echo=False,
    pool_pre_ping=True,
)

_TestSession = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Per-test temporary upload directory.

    Patches ``settings.upload_dir`` on the shared settings singleton so that
    the document route and service write to this directory instead of the
    configured default.  monkeypatch restores the original value on teardown.
    """
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(_settings, "upload_dir", str(upload_dir))
    return upload_dir


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped session whose changes are rolled back after each test.

    ``join_transaction_mode="create_savepoint"`` makes the session issue
    SAVEPOINT / RELEASE SAVEPOINT rather than real BEGIN / COMMIT, so service
    code that calls ``session.commit()`` does not actually persist to the DB.
    The outer connection-level transaction is rolled back on teardown.
    """
    async with _test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest_asyncio.fixture
async def seeded_data(db_session: AsyncSession) -> None:
    """
    Ensures the test admin user and invoice_processing workflow exist within
    the current test's session.

    Idempotent: checks before inserting.  Both rows roll back with the session
    at the end of the test — the database is never permanently modified.
    """
    admin_email = _settings.seed_admin_email
    admin_password = _settings.seed_admin_password or "AdminPass123!"

    result = await db_session.execute(select(User).where(User.email == admin_email))
    if result.scalar_one_or_none() is None:
        db_session.add(
            User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                full_name="Test Admin",
                role="admin",
                is_active=True,
            )
        )

    wf_result = await db_session.execute(
        select(Workflow).where(Workflow.slug == "invoice_processing")
    )
    if wf_result.scalar_one_or_none() is None:
        db_session.add(
            Workflow(
                name="Invoice Processing",
                slug="invoice_processing",
                description="Extract invoice fields from uploaded documents.",
                is_active=True,
            )
        )

    await db_session.flush()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    seeded_data: None,
    tmp_upload_dir: Path,
) -> AsyncGenerator[AsyncClient, None]:
    """
    httpx AsyncClient wired to the FastAPI app.

    - ``get_db`` is overridden to inject the per-test rolled-back session, so
      all DB operations during a request share the same transaction.
    - ``upload_dir`` is pointed at a temp directory (via ``tmp_upload_dir``).
    """

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """
    A fresh non-admin user for upload tests.

    Uses a random suffix so the email never collides within a session that
    might run tests in parallel.  Rolled back with the session.
    """
    user = User(
        email=f"testuser-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("password123"),
        full_name="Test User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_token(test_user: User) -> str:
    """
    Valid JWT for ``test_user``, generated with the same logic as the real
    login endpoint.  No round-trip to ``/auth/login`` needed.
    """
    return create_access_token({"sub": str(test_user.id)})

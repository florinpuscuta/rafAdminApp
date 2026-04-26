"""
Root conftest pentru test suite-ul backend-ului.

Strategie izolare:
- Session-scoped: (1) setăm APP_ENV=test + JWT_SECRET fix ÎNAINTE să importăm
  app.core.config, (2) creăm un DB separat `adeplast_saas_test` pe Postgres-ul
  local, (3) ridicăm schema prin SQLAlchemy metadata (rapid, fără Alembic —
  testele nu validează migrațiile per se), (4) la teardown DROP DATABASE.
- Function-scoped (autouse): TRUNCATE bulk la toate tabelele aplicative
  după fiecare test. Alegere vs. "SAVEPOINT + rollback": router-ele apelează
  explicit `session.commit()` (auth.signup, stores.create_alias, etc.) deci
  un SAVEPOINT async cu SQLAlchemy 2.x e fragil; TRUNCATE pe o sută de
  rânduri e imperceptibil ca timp și e 100% robust.
- Monkey-patch `app.core.db.engine` + `SessionLocal` către DB-ul test — toate
  endpointurile care folosesc `Depends(get_session)` primesc automat sesiunea
  corectă, fără `dependency_overrides`.
"""
from __future__ import annotations

import os

# IMPORTANT: setăm env ÎNAINTE de orice import din app.*, ca `Settings` să
# le citească la construcție. pydantic-settings face cache după prima instanță.
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key-do-not-use-in-prod"
# Cache Redis dezactivat în teste — fiecare test rulează izolat și nu vrem
# rezultate stale din rulări anterioare.
os.environ["CACHE_ENABLED"] = "False"
# Host-ul Postgres: `db` în container (docker-compose), `localhost` pe CI/host.
_DB_HOST = os.environ.get("TEST_DB_HOST", "db")
# Override FORCED — nu `setdefault` (ar păstra DATABASE_URL din .env care pointă la prod DB)
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://postgres:postgres@{_DB_HOST}:5432/adeplast_saas_test"
)

from typing import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# Acum safe să importăm din app.
from app.core import db as core_db
from app.core.config import settings
from app.core.db import Base
from app.main import app as fastapi_app


ADMIN_DB_URL = f"postgresql+asyncpg://postgres:postgres@{_DB_HOST}:5432/postgres"
TEST_DB_NAME = "adeplast_saas_test"
TEST_DB_URL = f"postgresql+asyncpg://postgres:postgres@{_DB_HOST}:5432/{TEST_DB_NAME}"


# ---------------------------------------------------------------------------
# DB lifecycle — create test DB + run schema, drop la final
# ---------------------------------------------------------------------------


async def _drop_and_create_test_db() -> None:
    """Conectare la `postgres` (admin DB) ca să putem DROP+CREATE DB-ul de test."""
    admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        # kick any lingering connections
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :n AND pid <> pg_backend_pid()"
            ),
            {"n": TEST_DB_NAME},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin_engine.dispose()


async def _drop_test_db() -> None:
    admin_engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :n AND pid <> pg_backend_pid()"
            ),
            {"n": TEST_DB_NAME},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
    await admin_engine.dispose()


async def _create_schema(engine) -> None:
    """Creăm schema direct din SQLAlchemy metadata.

    Alternative: `alembic upgrade head`. Folosim `create_all` fiindcă e mai
    rapid, nu depinde de configul alembic.ini și testele n-au nevoie să
    verifice migrațiile în sine (există teste separate pentru asta dacă e
    nevoie). Importul modelelor e garantat de alembic/env.py pattern.
    """
    # asigură import pentru toate modelele modulare
    import importlib
    import pkgutil

    import app.modules as modules_pkg

    for module_info in pkgutil.iter_modules(modules_pkg.__path__):
        if not module_info.ispkg:
            continue
        try:
            importlib.import_module(f"app.modules.{module_info.name}.models")
        except ModuleNotFoundError:
            continue

    # Custom PG enum types — modelele folosesc PG_ENUM(create_type=False)
    # ca să nu duplice cu Alembic. Pentru testele care nu rulează migrațiile,
    # le creăm manual înainte de metadata.create_all.
    enum_ddl = [
        (
            "organization_kind",
            "CREATE TYPE organization_kind AS ENUM ('production','demo','test')",
        ),
        (
            "user_role",
            "CREATE TYPE user_role AS ENUM "
            "('admin','director','finance_manager','regional_manager',"
            "'sales_agent','viewer')",
        ),
    ]
    async with engine.begin() as conn:
        for type_name, ddl in enum_ddl:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_type WHERE typname = :n"),
                {"n": type_name},
            )
            if exists.first() is None:
                await conn.execute(text(ddl))
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="session")
async def _test_db() -> AsyncIterator[None]:
    await _drop_and_create_test_db()

    # Engine pe DB-ul de test — folosit ca să creăm schema + ca engine global
    # pentru app. NullPool: fără connection pooling între teste — evită
    # "Future attached to a different loop" când pytest-asyncio creează un
    # event loop nou per test.
    test_engine = create_async_engine(TEST_DB_URL, future=True, poolclass=NullPool)
    await _create_schema(test_engine)

    # Monkey-patch engine + SessionLocal în app.core.db ca app-ul FastAPI
    # să scrie în DB-ul de test (nu în cel pe care pointa configul implicit).
    old_engine = core_db.engine
    old_session_local = core_db.SessionLocal

    core_db.engine = test_engine
    core_db.SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    # sync settings.database_url (folosit indirect prin alte componente)
    settings.database_url = TEST_DB_URL

    yield

    core_db.engine = old_engine
    core_db.SessionLocal = old_session_local
    await test_engine.dispose()
    await _drop_test_db()


# ---------------------------------------------------------------------------
# Per-test izolare: ȘTERGERE bulk a datelor tenant-scoped după fiecare test.
#
# Am evitat pattern-ul "nested transaction + rollback" fiindcă router-ele
# apelează explicit `session.commit()` (ex: auth.signup, stores.create_alias)
# iar async SQLAlchemy cu SAVEPOINT după commit e fragil. În schimb, ștergem
# rândurile din toate tabelele aplicative între teste — e rapid pentru suite-ul
# nostru (zeci de rânduri, nu milioane).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_session(_test_db) -> AsyncIterator[AsyncSession]:
    """Sesiune async folosibilă direct din teste (ex: pentru setup de fixtures)."""
    async with core_db.SessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function", autouse=True)
async def _cleanup_after_test(_test_db) -> AsyncIterator[None]:
    # resetează contorul slowapi (in-memory) ca testele să nu moștenească
    # rate-limit-ul altora. Fiecare test primește un X-Forwarded-For unic
    # via `client`, dar asta e o centură extra de siguranță.
    try:
        from app.core.rate_limit import limiter

        # slowapi 0.1.x: `.reset()` pe Limiter; fallback pe storage.reset()
        if hasattr(limiter, "reset"):
            limiter.reset()
        elif hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
            limiter._storage.reset()
    except Exception:  # pragma: no cover — API slowapi poate diferi între versiuni
        pass

    yield

    # TRUNCATE bulk: descoperim toate tabelele aplicative din metadata și
    # le truncăm CASCADE — robust față de schema în evoluție (ex. redenumire
    # tenants → organizations, tabele noi adăugate în refactor-uri).
    async with core_db.engine.begin() as conn:
        tables = list(reversed(Base.metadata.sorted_tables))
        if tables:
            tnames = ", ".join(f'"{t.name}"' for t in tables)
            await conn.execute(
                text(f"TRUNCATE TABLE {tnames} RESTART IDENTITY CASCADE")
            )


# ---------------------------------------------------------------------------
# HTTP client + rate limiter reset
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(_test_db) -> AsyncIterator[AsyncClient]:
    """AsyncClient pe ASGI-ul app-ului FastAPI (fără server HTTP real).

    Folosim `headers={"X-Forwarded-For": uuid}` ca slowapi (care rate-limit-uie
    per IP) să considere fiecare test o "adresă" separată — previne scurgeri
    între teste din contorul rate-limit. Testele care verifică explicit
    rate-limit-ul folosesc în schimb un IP fix.
    """
    unique_ip = f"127.{uuid4().int % 256}.{uuid4().int % 256}.{uuid4().int % 254 + 1}"
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
        headers={"X-Forwarded-For": unique_ip},
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth helper fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def signup_user(client: AsyncClient):
    """Factory: creează un user via /signup și returnează (data, token, headers).

    Default role după signup = admin (owner al tenantului nou creat).
    """

    async def _make(
        *,
        tenant_name: str = "Acme Test",
        email: str | None = None,
        password: str = "Parola_Test_1234",
    ):
        if email is None:
            email = f"owner-{uuid4().hex[:8]}@example.com"
        resp = await client.post(
            "/api/auth/signup",
            json={"tenantName": tenant_name, "email": email, "password": password},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        token = data["accessToken"]
        headers = {"Authorization": f"Bearer {token}"}
        return {
            "data": data,
            "token": token,
            "headers": headers,
            "email": email,
            "password": password,
            "tenant": data["tenant"],
            "user": data["user"],
        }

    return _make


@pytest_asyncio.fixture
async def admin_ctx(signup_user):
    """Un admin simplu, ready-to-use, cu token + headers."""
    return await signup_user()

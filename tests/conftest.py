"""
Spin up Postgres (testcontainers), set env, bind SQLAlchemy, create tables, then tests import `main`.

Must run before `app.db.session` is first imported so the engine uses the test DB.
"""

from __future__ import annotations

import atexit
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

# --- Postgres (session-wide) -------------------------------------------------
_pg = PostgresContainer("postgres:16-alpine")
_pg.start()
atexit.register(_pg.stop)

_raw_url = _pg.get_connection_url()
# Project uses psycopg (v3); testcontainers defaults to psycopg2 in the URL.
DATABASE_URL = _raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "pytest-jwt-secret-key-min-32-chars-x")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

import app.db.session as _session_mod  # noqa: E402

if _session_mod.engine is not None:
    _session_mod.engine.dispose()
_session_mod.settings = get_settings()
_session_mod.engine = create_engine(
    _session_mod.settings.database_url,
    pool_pre_ping=True,
)
_session_mod.SessionLocal = sessionmaker(
    bind=_session_mod.engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

from app.db.schema import ensure_schema  # noqa: E402

ensure_schema()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(client, email: str, *, password: str = "test-password-1", name: str = "Test User"):
    r = client.post(
        "/auth/register",
        json={"full_name": name, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    return r.json()


def login_token(client, email: str, password: str = "test-password-1") -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def create_org(client, token: str, org_name: str = "Acme") -> int:
    r = client.post(
        "/organizations/",
        json={"org_name": org_name},
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["org_id"]


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as c:
        yield c

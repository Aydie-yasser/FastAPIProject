"""Authentication: identity via JWT + login; invalid/missing credentials rejected."""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import auth_headers, login_token, register_user


def test_register_then_login_returns_token(client):
    register_user(client, "auth_user@example.com")
    token = login_token(client, "auth_user@example.com")
    assert isinstance(token, str) and len(token) > 20


def test_login_wrong_password_401(client):
    register_user(client, "pw_user@example.com", password="correct-secret")
    r = client.post(
        "/auth/login",
        json={"email": "pw_user@example.com", "password": "wrong-secret"},
    )
    assert r.status_code == 401


def test_invalid_token_cannot_access_protected_route(client):
    register_user(client, "tok_user@example.com")
    r = client.post(
        "/organizations/",
        json={"org_name": "Org"},
        headers=auth_headers("not-a-real.jwt.token"),
    )
    assert r.status_code == 401


def test_missing_token_cannot_create_org(client):
    r = client.post("/organizations/", json={"org_name": "No Auth Org"})
    assert r.status_code in (401, 403)


def test_deleted_user_id_in_token_gets_401(client):
    """Token decodes but user row missing → deps treat as unauthorized."""
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.user import User

    register_user(client, "gone@example.com")
    token = login_token(client, "gone@example.com")
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.email == "gone@example.com")).scalar_one()
        db.delete(u)
        db.commit()

    r = client.post(
        "/organizations/",
        json={"org_name": "After Delete"},
        headers=auth_headers(token),
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_root_async_client():
    """pytest-asyncio: async HTTP client against the ASGI app."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200
    assert "Hello" in r.json().get("message", "")

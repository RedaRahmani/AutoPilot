from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_login_success(client):
    response = await client.post(
        "/auth/login",
        json={
            "email": settings.seed_admin_email,
            "password": settings.seed_admin_password,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    response = await client.post(
        "/auth/login",
        json={
            "email": settings.seed_admin_email,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client):
    login_response = await client.post(
        "/auth/login",
        json={
            "email": settings.seed_admin_email,
            "password": settings.seed_admin_password,
        },
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == settings.seed_admin_email.lower()
    assert body["role"] == "admin"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token_returns_401(client):
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_token_returns_204(client):
    login_response = await client.post(
        "/auth/login",
        json={
            "email": settings.seed_admin_email,
            "password": settings.seed_admin_password,
        },
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    expired_payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
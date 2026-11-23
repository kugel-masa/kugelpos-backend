# Copyright 2026 masa@kugel
"""E2E coverage for the account service's authentication endpoints.

Drives the live account service (uvicorn behind localhost:8000) to
verify that the registration / login / sub-user-registration flows work
against a real MongoDB. The integration tier already covers these via
ASGITransport; this tier adds the same coverage against the running
process so we catch packaging / wiring / startup issues that the
in-process tests can't.
"""
import os
import uuid

import pytest
from fastapi import status

# POST /accounts/register requires the tenant provisioning key (issue #138)
PROVISIONING_HEADERS = {
    "X-Provisioning-Key": os.environ.get(
        "TENANT_PROVISIONING_KEY", "dev-tenant-provisioning-key-for-development-only"
    )
}


def _new_tenant_id() -> str:
    """Generate a fresh tenant ID per test so DB drops in conftest don't
    collide with concurrent runs."""
    return "E2E-" + uuid.uuid4().hex[:8].upper()


@pytest.mark.asyncio
async def test_register_superuser_then_token(http_client):
    """POST /register creates a tenant + admin user, then POST /token
    returns a JWT for that admin."""
    tenant_id = _new_tenant_id()
    password = "e2e-pw-" + uuid.uuid4().hex[:8]

    response = await http_client.post(
        "/api/v1/accounts/register",
        headers=PROVISIONING_HEADERS,
        json={"username": "admin", "password": password, "tenant_id": tenant_id},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["username"] == "admin"
    assert body["data"]["tenantId"] == tenant_id
    assert body["data"]["isSuperuser"] is True

    response = await http_client.post(
        "/api/v1/accounts/token",
        data={"username": "admin", "password": password, "client_id": tenant_id},
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    token_body = response.json()
    assert token_body.get("access_token")
    assert token_body.get("token_type") == "bearer"


@pytest.mark.asyncio
async def test_register_without_tenant_id_generates_one(http_client):
    """POST /register without tenant_id yields a server-generated tenant ID."""
    response = await http_client.post(
        "/api/v1/accounts/register",
        headers=PROVISIONING_HEADERS,
        json={"username": "admin", "password": "pw"},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    generated = response.json()["data"]["tenantId"]
    assert generated, "tenantId should have been generated"


@pytest.mark.asyncio
async def test_register_user_by_superuser(http_client):
    """POST /register/user lets a superuser create a regular user."""
    tenant_id = _new_tenant_id()
    password = "admin-pw"

    response = await http_client.post(
        "/api/v1/accounts/register",
        headers=PROVISIONING_HEADERS,
        json={"username": "admin", "password": password, "tenant_id": tenant_id},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    response = await http_client.post(
        "/api/v1/accounts/token",
        data={"username": "admin", "password": password, "client_id": tenant_id},
    )
    assert response.status_code == status.HTTP_200_OK
    admin_token = response.json()["access_token"]

    sub_username = "user-" + uuid.uuid4().hex[:6]
    response = await http_client.post(
        f"/api/v1/accounts/register/user?tenant_id={tenant_id}",
        json={"username": sub_username, "password": "user-pw"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["data"]["username"] == sub_username
    assert response.json()["data"]["isSuperuser"] is False
    assert response.json()["data"]["tenantId"] == tenant_id

    # Registering the same username again hits the unique index. The 500 used
    # to return the driver's text in `data`, the duplicated key values with it
    # (#318); the text now stays in the log.
    response = await http_client.post(
        f"/api/v1/accounts/register/user?tenant_id={tenant_id}",
        json={"username": sub_username, "password": "user-pw"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert response.json()["data"] is None
    assert "dup key" not in response.text
    assert sub_username not in response.text


@pytest.mark.asyncio
async def test_token_with_bad_password_returns_401(http_client):
    """POST /token with wrong password -> 401."""
    tenant_id = _new_tenant_id()
    response = await http_client.post(
        "/api/v1/accounts/register",
        headers=PROVISIONING_HEADERS,
        json={"username": "admin", "password": "correct-pw", "tenant_id": tenant_id},
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = await http_client.post(
        "/api/v1/accounts/token",
        data={"username": "admin", "password": "wrong-pw", "client_id": tenant_id},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [{}, {"X-Provisioning-Key": "not-the-key"}], ids=["missing", "wrong"])
async def test_register_without_the_provisioning_key_is_refused(http_client, headers):
    """POST /register creates a tenant and a superuser and takes no user token,
    so it requires the deployment's provisioning key (issue #138)."""
    response = await http_client.post(
        "/api/v1/accounts/register",
        headers=headers,
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

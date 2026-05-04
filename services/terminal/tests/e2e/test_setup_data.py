# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""E2E tier setup: create tenant + store + terminal via the live terminal
service.

Why this lives in e2e:
- POST /api/v1/tenants on the terminal service fans out to master-data,
  cart, report, journal, and stock to create their per-tenant DBs.
  Mocking that fan-out (as the integration tier does) gives us isolated
  unit-of-work coverage but leaves downstream services with nothing.
- Other services' e2e tests (cart, report, etc.) reach for
  `terminals/{terminal_id}` to grab the API key during their conftest
  auth bootstrap; without this setup they error at fixture collection.

The test is idempotent: re-running it against an already-populated stack
treats 400 "already exists" as success.

run_e2e_tests.sh orders services as:
  account → terminal → master-data → journal → stock → report → cart
so this setup runs before any service that depends on the tenant.
"""
import os

import pytest
from fastapi import status
from httpx import AsyncClient


TENANT_NAME = "Test Tenant"
STORE_CODE = "5678"
STORE_NAME = "Test Store"
TERMINAL_NO = 9


async def _get_admin_token(tenant_id: str, account_base_url: str) -> str:
    token_url = f"{account_base_url}/api/v1/accounts/token"
    login_data = {"username": "admin", "password": "admin", "client_id": tenant_id}
    async with AsyncClient() as client:
        response = await client.post(url=token_url, data=login_data)
    assert response.status_code == status.HTTP_200_OK, (
        f"Failed to login admin: {response.status_code} {response.text}"
    )
    token = response.json().get("access_token")
    assert token, "No access_token in login response"
    return token


@pytest.mark.asyncio
async def test_setup_tenant_store_terminal(http_client):
    """Create the tenant, store, and terminal that other e2e tests depend on.

    Idempotent — already-exists responses are treated as success so the
    test can be re-run against a populated stack.
    """
    tenant_id = os.environ.get("TENANT_ID")
    account_base_url = os.environ.get("BASE_URL_ACCOUNT")
    assert tenant_id, "TENANT_ID env var is required"
    assert account_base_url, "BASE_URL_ACCOUNT env var is required"

    token = await _get_admin_token(tenant_id, account_base_url)
    header = {"Authorization": f"Bearer {token}"}

    response = await http_client.post(
        "/api/v1/tenants",
        json={
            "tenant_id": tenant_id,
            "tenant_name": TENANT_NAME,
            "stores": [],
            "tags": ["e2e-setup"],
        },
        headers=header,
    )
    assert response.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
    ), f"Unexpected status creating tenant: {response.status_code} {response.text}"
    if response.status_code == status.HTTP_400_BAD_REQUEST:
        assert "already exists" in response.text.lower() or "duplicate" in response.text.lower(), (
            f"Tenant create returned 400 but not for already-exists: {response.text}"
        )

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores",
        json={"store_code": STORE_CODE, "store_name": STORE_NAME, "tags": ["e2e-setup"]},
        headers=header,
    )
    assert response.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
    ), f"Unexpected status creating store: {response.status_code} {response.text}"

    response = await http_client.post(
        "/api/v1/terminals",
        json={
            "store_code": STORE_CODE,
            "terminal_no": TERMINAL_NO,
            "description": "E2E Test Terminal",
        },
        headers=header,
    )
    assert response.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
    ), f"Unexpected status creating terminal: {response.status_code} {response.text}"

    expected_terminal_id = f"{tenant_id}-{STORE_CODE}-{TERMINAL_NO}"
    response = await http_client.get(f"/api/v1/terminals/{expected_terminal_id}", headers=header)
    assert response.status_code == status.HTTP_200_OK, (
        f"Terminal {expected_terminal_id} not retrievable after setup: "
        f"{response.status_code} {response.text}"
    )
    data = response.json().get("data")
    assert data, f"Terminal GET returned no data: {response.json()}"
    assert data.get("terminalId") == expected_terminal_id
    assert data.get("apiKey"), "Terminal record has no apiKey"

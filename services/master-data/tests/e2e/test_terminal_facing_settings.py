# Copyright 2026 masa@kugel
"""Terminal-facing settings are readable over the API (issue #174).

Since #166 the terminal derives its printed receipt number from the configured
range, so it has to read that range. A service that finds no settings record
falls back to its own configuration, but that fallback is invisible here - the
endpoint answers 404 - so tenant setup seeds the values a client must see.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status

# The shipped defaults; a tenant that overrides them stores its own value.
EXPECTED_DEFAULTS = {"RECEIPT_NO_START_VALUE": "111111", "RECEIPT_NO_END_VALUE": "999999"}


@pytest_asyncio.fixture(autouse=True)
async def _tenant_is_set_up(http_client, admin_header):
    """Make the file self-sufficient.

    The session fixture drops the tenant database, and the seeding happens in
    tenant setup - so running this file on its own would otherwise assert
    against a tenant that was never initialised. POST /tenants is idempotent.
    """
    await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": os.environ.get("TENANT_ID")},
        headers=admin_header,
    )


async def _value(http_client, header, name):
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    return await http_client.get(
        f"/api/v1/tenants/{tenant_id}/settings/{name}/value?store_code={store_code}&terminal_no=9",
        headers=header,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("name,expected", EXPECTED_DEFAULTS.items())
async def test_receipt_range_is_readable(http_client, admin_header, name, expected):
    response = await _value(http_client, admin_header, name)

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["value"] == expected


@pytest.mark.asyncio
async def test_the_range_is_a_real_range(http_client, admin_header):
    start = int((await _value(http_client, admin_header, "RECEIPT_NO_START_VALUE")).json()["data"]["value"])
    end = int((await _value(http_client, admin_header, "RECEIPT_NO_END_VALUE")).json()["data"]["value"])

    assert end > start


@pytest.mark.asyncio
async def test_setup_is_rerunnable_without_disturbing_the_values(http_client, admin_header):
    """Tenant setup is how migrations reach an existing tenant, so re-running it
    must not overwrite what an operator configured."""
    tenant_id = os.environ.get("TENANT_ID")
    before = (await _value(http_client, admin_header, "RECEIPT_NO_START_VALUE")).json()["data"]["value"]

    response = await http_client.post("/api/v1/tenants", json={"tenant_id": tenant_id}, headers=admin_header)
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST), response.text

    after = (await _value(http_client, admin_header, "RECEIPT_NO_START_VALUE")).json()["data"]["value"]
    assert after == before

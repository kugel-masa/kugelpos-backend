# Copyright 2026 masa@kugel
"""CRUD smoke tests for master-data resources against the running service.

Covers the create / read / update / delete cycle for each major
resource type — items, payments, staff, categories — to ensure the
service is correctly wired end-to-end (HTTP routing, auth, MongoDB
write, response transformer).

Each test creates its own resource with a unique key so re-runs don't
collide and tests don't depend on each other.
"""
import os
import uuid

import pytest
from fastapi import status


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


@pytest.mark.asyncio
async def test_staff_crud(http_client, admin_header):
    """POST -> GET -> PUT -> GET -> DELETE on /staff."""
    tenant_id = os.environ.get("TENANT_ID")
    staff_id = _unique("S")

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/staff",
        json={"id": staff_id, "name": "E2E Staff", "pin": "1234", "roles": ["staff"]},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/staff/{staff_id}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["name"] == "E2E Staff"

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/staff/{staff_id}",
        json={"id": staff_id, "name": "E2E Staff Updated", "pin": "9999", "roles": ["staff"]},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["name"] == "E2E Staff Updated"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/staff/{staff_id}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_category_crud(http_client, admin_header):
    """POST -> GET (list + by code) -> PUT -> DELETE on /categories."""
    tenant_id = os.environ.get("TENANT_ID")
    category_code = _unique("C")[:5]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        json={
            "categoryCode": category_code,
            "description": "E2E Cat",
            "descriptionShort": "EC",
            "taxCode": "01",
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/categories/{category_code}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["categoryCode"] == category_code

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/categories", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK
    assert any(c["categoryCode"] == category_code for c in response.json()["data"])

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/categories/{category_code}",
        json={
            "categoryCode": category_code,
            "description": "E2E Cat Updated",
            "descriptionShort": "ECU",
            "taxCode": "01",
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/categories/{category_code}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_item_crud(http_client, admin_header):
    """POST -> GET (list + by code) -> PUT -> DELETE on /items.

    Items reference a tax_code and category_code; we use the defaults
    seeded by tenant setup ('01' tax, no category constraint).
    """
    tenant_id = os.environ.get("TENANT_ID")
    item_code = _unique("ITEM")

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/items",
        json={
            "itemCode": item_code,
            "description": "E2E Item",
            "unitPrice": 200.0,
            "unitCost": 100.0,
            "taxCode": "01",
            "categoryCode": "001",
            "itemDetails": [],
            "imageUrls": [],
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/items/{item_code}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["unitPrice"] == 200.0

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/items", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK
    assert any(i["itemCode"] == item_code for i in response.json()["data"])

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/items/{item_code}",
        json={
            "itemCode": item_code,
            "description": "E2E Item Updated",
            "unitPrice": 250.0,
            "unitCost": 100.0,
            "taxCode": "01",
            "categoryCode": "001",
            "itemDetails": [],
            "imageUrls": [],
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["unitPrice"] == 250.0

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/items/{item_code}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_payment_crud(http_client, admin_header):
    """POST -> GET -> PUT -> DELETE on /payments."""
    tenant_id = os.environ.get("TENANT_ID")
    payment_code = _unique("P")[:4]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/payments",
        json={
            "paymentCode": payment_code,
            "description": "E2E Pay",
            "limitAmount": 0.0,
            "canRefund": True,
            "canDepositOver": True,
            "canChange": True,
            "isActive": True,
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/payments/{payment_code}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/payments/{payment_code}",
        json={
            "paymentCode": payment_code,
            "description": "E2E Pay Updated",
            "limitAmount": 0.0,
            "canRefund": True,
            "canDepositOver": True,
            "canChange": True,
            "isActive": True,
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["description"] == "E2E Pay Updated"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/payments/{payment_code}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_taxes_read(http_client, admin_header):
    """GET /taxes lists tax codes seeded at tenant init."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/taxes", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert isinstance(data, list)
    assert any(t["taxCode"] == "01" for t in data)


@pytest.mark.asyncio
async def test_settings_create_and_read(http_client, admin_header):
    """POST /settings then GET /settings/{name}/value."""
    tenant_id = os.environ.get("TENANT_ID")
    setting_name = _unique("E2E_SETTING").upper()
    store_code = "5678"

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/settings",
        json={
            "name": setting_name,
            "defaultValue": "default-val",
            "values": [
                {"storeCode": store_code, "value": "store-val"},
            ],
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/settings/{setting_name}/value"
        f"?store_code={store_code}&terminal_no=9",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["value"] == "store-val"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/settings/{setting_name}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK

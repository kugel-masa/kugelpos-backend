# Copyright 2026 masa@kugel
"""E2E setup for master-data: tenant init + canonical seed data.

Runs first (collection-ordered to test_setup_data) so subsequent e2e
tests have the tenant DB initialised AND the canonical staff/item/
payment data that cart and report e2e tests expect (49-01 etc).
"""
import os

import pytest
from fastapi import status


def _ok(resp, *codes):
    """Idempotent setup helper — accept the listed codes (typically 200/201
    for success, 400 for already-exists)."""
    assert resp.status_code in codes, f"Setup step failed: {resp.status_code} {resp.text}"


@pytest.mark.asyncio
async def test_master_data_tenant_setup(http_client, admin_header):
    """POST /tenants then seed staff / category / items / payments so
    cart + report e2e tests have the data they reference."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")

    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id},
        headers=admin_header,
    )
    _ok(response, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

    # Staff S001 — used by cart/terminal sign-in flows
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/staff",
        json={"id": "S001", "name": "Staff1", "pin": "1234", "roles": ["staff"]},
        headers=admin_header,
    )
    _ok(response, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

    # Category 001
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/categories",
        json={
            "categoryCode": "001",
            "description": "Category1",
            "descriptionShort": "Cat1",
            "taxCode": "01",
        },
        headers=admin_header,
    )
    _ok(response, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

    # Items 49-01, 49-02
    for item_code, name, price in [
        ("49-01", "Item1", 120.0),
        ("49-02", "Item2", 280.0),
    ]:
        response = await http_client.post(
            f"/api/v1/tenants/{tenant_id}/items",
            json={
                "itemCode": item_code, "description": name,
                "unitPrice": price, "unitCost": price / 2,
                "taxCode": "01", "categoryCode": "001",
                "itemDetails": [], "imageUrls": [],
            },
            headers=admin_header,
        )
        _ok(response, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

    # ItemStore 49-01 with store_price=100 (cart e2e expects this price)
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        json={"itemCode": "49-01", "storePrice": 100.0},
        headers=admin_header,
    )
    _ok(
        response,
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
        # Store may not exist yet — terminal e2e will create it. Ignore 404.
        status.HTTP_404_NOT_FOUND,
    )

    # Payments — Cash (01), Cashless (11), Others (12)
    for code, desc, limit in [
        ("01", "Cash", 0.0),
        ("11", "Cashless", 100000.0),
        ("12", "Others", 100000.0),
    ]:
        response = await http_client.post(
            f"/api/v1/tenants/{tenant_id}/payments",
            json={
                "paymentCode": code, "description": desc,
                "limitAmount": limit,
                "canRefund": code == "01",
                "canDepositOver": code == "01",
                "canChange": code == "01",
                "isActive": True,
            },
            headers=admin_header,
        )
        _ok(response, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST)

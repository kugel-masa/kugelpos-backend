# Copyright 2026 masa@kugel
"""E2E coverage for master-data resources not exercised by
test_crud_smoke.py — item_books (4-level deep CRUD), promotions, and
settings list / by-name reads.
"""
import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import status


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


@pytest.mark.asyncio
async def test_item_book_full_lifecycle(http_client, admin_header):
    """Create → modify each level (book → category → tab → button) → delete in
    reverse order. Covers the 8 PUT/DELETE endpoints + the 4 POST endpoints."""
    tenant_id = os.environ.get("TENANT_ID")
    h = admin_header

    # Create book
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books",
        json={"title": "E2E Book", "categories": []},
        headers=h,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text
    book_id = r.json()["data"]["itemBookId"]

    # List books (GET)
    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/item_books", headers=h)
    assert r.status_code == status.HTTP_200_OK
    assert any(b["itemBookId"] == book_id for b in r.json()["data"])

    # Get by id
    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/item_books/{book_id}", headers=h)
    assert r.status_code == status.HTTP_200_OK

    # Get detail (with optional store_code query)
    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/detail?store_code=5678",
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK

    # Update book title
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}",
        json={"title": "E2E Book Updated", "categories": []},
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK

    # Add category
    cat_no = 11
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories",
        json={"categoryNumber": cat_no, "title": "Food", "color": "0xFFFFFF", "tabs": []},
        headers=h,
    )
    assert r.status_code == status.HTTP_201_CREATED

    # Update category
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}",
        json={"categoryNumber": cat_no, "title": "Drinks", "color": "0xFF0000", "tabs": []},
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK

    # Add tab
    tab_no = 1
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}/tabs",
        json={"tabNumber": tab_no, "title": "Lunch", "color": "0xF0FFFF", "buttons": []},
        headers=h,
    )
    assert r.status_code == status.HTTP_201_CREATED

    # Update tab
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}/tabs/{tab_no}",
        json={"tabNumber": tab_no, "title": "Dinner", "color": "0x00FF00", "buttons": []},
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK

    # Add button
    pos_x, pos_y = 1, 1
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}/tabs/{tab_no}/buttons",
        json={
            "pos_x": pos_x, "pos_y": pos_y, "size": "Single",
            "imageUrl": "url", "colorText": "0xF0FFFF", "itemCode": "49-01",
        },
        headers=h,
    )
    assert r.status_code == status.HTTP_201_CREATED

    # Update button
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}/tabs/{tab_no}/buttons/pos_x/{pos_x}/pos_y/{pos_y}",
        json={
            "pos_x": pos_x, "pos_y": pos_y, "size": "DoubleWidth",
            "imageUrl": "new-url", "colorText": "0x0000FF", "itemCode": "49-02",
        },
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK

    # Delete in reverse: button → tab → category → book
    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}/tabs/{tab_no}/buttons/pos_x/{pos_x}/pos_y/{pos_y}",
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK
    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}/tabs/{tab_no}",
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK
    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}/categories/{cat_no}",
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK
    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{book_id}",
        headers=h,
    )
    assert r.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_promotion_crud(http_client, admin_header):
    """POST → GET (list, by code, active) → PUT → DELETE on /promotions."""
    tenant_id = os.environ.get("TENANT_ID")
    promo_code = _unique("PROMO")
    now = datetime.now()
    start = now.isoformat()
    end = (now + timedelta(days=30)).isoformat()

    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/promotions",
        json={
            "promotionCode": promo_code,
            "promotionType": "category_discount",
            "name": "E2E Promo",
            "description": "E2E test",
            "startDatetime": start,
            "endDatetime": end,
            "isActive": True,
            "detail": {"targetCategoryCodes": ["001"], "discountRate": 10.0},
        },
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text

    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/promotions", headers=admin_header)
    assert r.status_code == status.HTTP_200_OK
    assert any(p["promotionCode"] == promo_code for p in r.json()["data"])

    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/{promo_code}", headers=admin_header
    )
    assert r.status_code == status.HTTP_200_OK

    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/promotions/active", headers=admin_header
    )
    assert r.status_code == status.HTTP_200_OK

    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/promotions/{promo_code}",
        json={
            "name": "E2E Promo Updated",
            "description": "updated",
            "startDatetime": start,
            "endDatetime": end,
            "isActive": False,
            "detail": {"targetCategoryCodes": ["001"], "discountRate": 5.0},
        },
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/promotions/{promo_code}", headers=admin_header
    )
    assert r.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_settings_list_and_by_name(http_client, admin_header):
    """GET /settings (list) and GET /settings/{name} (no /value suffix)."""
    tenant_id = os.environ.get("TENANT_ID")
    name = _unique("SET").upper().replace("-", "_")

    # Create
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/settings",
        json={"name": name, "defaultValue": "v", "values": []},
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text

    # List
    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/settings", headers=admin_header)
    assert r.status_code == status.HTTP_200_OK
    assert any(s["name"] == name for s in r.json()["data"])

    # Get by name
    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/settings/{name}", headers=admin_header
    )
    assert r.status_code == status.HTTP_200_OK

    # Update
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/settings/{name}",
        json={"name": name, "defaultValue": "v2", "values": []},
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_200_OK

    # Cleanup
    await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/settings/{name}", headers=admin_header
    )


@pytest.mark.asyncio
async def test_taxes_by_code(http_client, admin_header):
    """GET /taxes/{tax_code} returns the seeded tax record."""
    tenant_id = os.environ.get("TENANT_ID")
    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/taxes/01", headers=admin_header
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["taxCode"] == "01"


@pytest.mark.asyncio
async def test_store_items_listing(http_client, admin_header):
    """GET /tenants/{tid}/stores/{sc}/items lists items for the store."""
    tenant_id = os.environ.get("TENANT_ID")
    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/items", headers=admin_header
    )
    # Either 200 (with whatever rows are present) or 404 if no items linked.
    assert r.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND), r.text


@pytest.mark.asyncio
async def test_store_item_get_with_details(http_client, admin_header):
    """GET /tenants/{tid}/stores/{sc}/items/{ic}/details returns the
    enriched item view if the item-store record exists."""
    tenant_id = os.environ.get("TENANT_ID")
    # Use canonical 49-01 which the setup test seeded an item-store record for.
    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/5678/items/49-01/details", headers=admin_header
    )
    assert r.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND), r.text


@pytest.mark.asyncio
async def test_payments_and_staff_lists(http_client, admin_header):
    """GET /payments and GET /staff return their respective lists."""
    tenant_id = os.environ.get("TENANT_ID")

    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/payments", headers=admin_header)
    assert r.status_code == status.HTTP_200_OK, r.text
    assert isinstance(r.json()["data"], list)

    r = await http_client.get(f"/api/v1/tenants/{tenant_id}/staff", headers=admin_header)
    assert r.status_code == status.HTTP_200_OK, r.text
    assert isinstance(r.json()["data"], list)


@pytest.mark.asyncio
async def test_store_item_full_crud(http_client, admin_header):
    """POST -> GET (without /details) -> PUT -> DELETE on
    /tenants/{tid}/stores/{sc}/items/{ic}.

    Uses a fresh item to avoid clobbering the canonical 49-01 record.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = "5678"
    item_code = _unique("SI")

    # Need an item record before linking it to a store.
    await http_client.post(
        f"/api/v1/tenants/{tenant_id}/items",
        json={
            "itemCode": item_code, "description": "Store-Item E2E",
            "unitPrice": 150.0, "unitCost": 75.0,
            "taxCode": "01", "categoryCode": "001",
            "itemDetails": [], "imageUrls": [],
        },
        headers=admin_header,
    )

    # Create the store-item link
    r = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        json={"itemCode": item_code, "storePrice": 130.0},
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text

    # Read the bare store-item record (no /details suffix)
    r = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}",
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["storePrice"] == 130.0

    # Update
    r = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}",
        json={"itemCode": item_code, "storePrice": 140.0},
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["data"]["storePrice"] == 140.0

    # Delete
    r = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items/{item_code}",
        headers=admin_header,
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    # Cleanup the item
    await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/items/{item_code}", headers=admin_header
    )

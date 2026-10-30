# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for item_books PUT / DELETE — the 8 endpoints not
yet exercised by test_operations.py:

  PUT/DELETE  /tenants/{tid}/item_books/{ibid}
  PUT/DELETE  /tenants/{tid}/item_books/{ibid}/categories/{cn}
  PUT/DELETE  /tenants/{tid}/item_books/{ibid}/categories/{cn}/tabs/{tn}
  PUT/DELETE  /tenants/{tid}/item_books/{ibid}/categories/{cn}/tabs/{tn}/buttons/pos_x/{px}/pos_y/{py}

Each test is self-contained: creates its own item_book hierarchy, mutates
it, and (for delete tests) verifies the resource is gone.
"""
import os

import pytest
from fastapi import status


@pytest.fixture
def category_number():
    return 7


@pytest.fixture
def tab_number():
    return 1


async def _ensure_tenant(http_client, header, tenant_id):
    """Idempotent tenant create — 400 with already-exists is fine."""
    response = await http_client.post(
        "/api/v1/tenants", json={"tenantId": tenant_id}, headers=header
    )
    assert response.status_code in (
        status.HTTP_201_CREATED,
        status.HTTP_400_BAD_REQUEST,
    )


async def _create_item_book(http_client, header, tenant_id, title="Lifecycle Menu"):
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books",
        json={"title": title, "categories": []},
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["data"]["itemBookId"]


async def _add_category(http_client, header, tenant_id, item_book_id, category_number):
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories",
        json={
            "categoryNumber": category_number,
            "title": "food",
            "color": "0xF0FFFF",
            "tabs": [],
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED


async def _add_tab(http_client, header, tenant_id, item_book_id, category_number, tab_number):
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs",
        json={
            "tabNumber": tab_number,
            "title": "lunch",
            "color": "0xF0FFFF",
            "buttons": [],
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED


async def _add_button(
    http_client, header, tenant_id, item_book_id, category_number, tab_number, pos_x, pos_y, item_code="49-01"
):
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons",
        json={
            "pos_x": pos_x,
            "pos_y": pos_y,
            "size": "Single",
            "imageUrl": "url1",
            "colorText": "0xF0FFFF",
            "itemCode": item_code,
        },
        headers=header,
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.asyncio
async def test_item_book_put_delete(http_client, admin_header):
    """PUT and DELETE on the item_book root resource."""
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)
    item_book_id = await _create_item_book(http_client, admin_header, tenant_id, title="Original Title")

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}",
        json={"title": "Updated Title", "categories": []},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["title"] == "Updated Title"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_item_book_category_put_delete(http_client, admin_header, category_number):
    """PUT and DELETE on a category nested inside an item_book."""
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)
    item_book_id = await _create_item_book(http_client, admin_header, tenant_id, title="Cat Test")
    await _add_category(http_client, admin_header, tenant_id, item_book_id, category_number)

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}",
        json={
            "categoryNumber": category_number,
            "title": "drinks",
            "color": "0xFF0000",
            "tabs": [],
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    cat = response.json()["data"]["categories"][0]
    assert cat["title"] == "drinks"
    assert cat["color"] == "0xFF0000"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    cats = response.json()["data"].get("categories", [])
    assert all(c["categoryNumber"] != category_number for c in cats)


@pytest.mark.asyncio
async def test_item_book_tab_put_delete(http_client, admin_header, category_number, tab_number):
    """PUT and DELETE on a tab nested two levels deep."""
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)
    item_book_id = await _create_item_book(http_client, admin_header, tenant_id, title="Tab Test")
    await _add_category(http_client, admin_header, tenant_id, item_book_id, category_number)
    await _add_tab(http_client, admin_header, tenant_id, item_book_id, category_number, tab_number)

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}",
        json={
            "tabNumber": tab_number,
            "title": "dinner",
            "color": "0x00FF00",
            "buttons": [],
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    tab = response.json()["data"]["categories"][0]["tabs"][0]
    assert tab["title"] == "dinner"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_item_book_button_put_delete(http_client, admin_header, category_number, tab_number):
    """PUT and DELETE on a button nested three levels deep."""
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)
    item_book_id = await _create_item_book(http_client, admin_header, tenant_id, title="Button Test")
    await _add_category(http_client, admin_header, tenant_id, item_book_id, category_number)
    await _add_tab(http_client, admin_header, tenant_id, item_book_id, category_number, tab_number)
    pos_x, pos_y = 1, 1
    await _add_button(
        http_client, admin_header, tenant_id, item_book_id, category_number, tab_number, pos_x, pos_y
    )

    response = await http_client.put(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}",
        json={
            "pos_x": pos_x,
            "pos_y": pos_y,
            "size": "DoubleWidth",
            "imageUrl": "url-updated",
            "colorText": "0x0000FF",
            "itemCode": "49-02",
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK
    btn = response.json()["data"]["categories"][0]["tabs"][0]["buttons"][0]
    assert btn["itemCode"] == "49-02"
    assert btn["size"] == "DoubleWidth"

    response = await http_client.delete(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}/categories/{category_number}/tabs/{tab_number}/buttons/pos_x/{pos_x}/pos_y/{pos_y}",
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK


# =========================================================================
# Creating with a populated tree (issue #197)
# =========================================================================


@pytest.mark.asyncio
async def test_create_item_book_with_a_populated_tree(http_client, admin_header):
    """The create request carries categories -> tabs -> buttons in one body.

    Every other test here creates with `"categories": []` and builds the tree
    afterwards through the sub-resource endpoints, so nothing exercised the
    shape the schema actually declares. The route handed the request's own
    Pydantic models to a service that builds ItemBookCategory(**category) from
    dicts, and answered an unhandled 500 for any book carrying a category.
    """
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)

    payload = {
        "title": "Spring Menu",
        "categories": [
            {
                "categoryNumber": 1,
                "title": "Drinks",
                "color": "#9AA5B1",
                "tabs": [
                    {
                        "tabNumber": 1,
                        "title": "Hot",
                        "color": "#E4E7EB",
                        "buttons": [
                            {
                                "posX": 0,
                                "posY": 0,
                                "size": "Single",
                                "imageUrl": "https://cdn.example.co.jp/coffee.webp",
                                "colorText": "#1F2933",
                                "itemCode": "49-01",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books", json=payload, headers=admin_header
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    item_book_id = response.json()["data"]["itemBookId"]

    # Read it back: the tree has to survive the round trip, not merely be accepted.
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/item_books/{item_book_id}", headers=admin_header
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    data = response.json()["data"]
    assert data["title"] == "Spring Menu"
    category = data["categories"][0]
    assert category["categoryNumber"] == 1
    assert category["title"] == "Drinks"
    tab = category["tabs"][0]
    assert tab["tabNumber"] == 1
    button = tab["buttons"][0]
    assert button["itemCode"] == "49-01"
    assert button["posX"] == 0
    assert button["size"] == "Single"


@pytest.mark.asyncio
async def test_create_item_book_with_several_categories(http_client, admin_header):
    """More than one category, so the per-entry conversion is exercised as a list."""
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)

    categories = [
        {
            "categoryNumber": n,
            "title": f"Category {n}",
            "color": "#9AA5B1",
            "tabs": [{"tabNumber": 1, "title": "T", "color": "#E4E7EB", "buttons": []}],
        }
        for n in (1, 2, 3)
    ]

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books",
        json={"title": "Multi", "categories": categories},
        headers=admin_header,
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert [c["categoryNumber"] for c in response.json()["data"]["categories"]] == [1, 2, 3]


# =========================================================================
# Display-only unit price and description
# =========================================================================


def _buttons(response):
    data = response.json()["data"]
    if isinstance(data, list):
        data = data[0]
    return {
        b["itemCode"]: (b["unitPrice"], b["description"])
        for c in data["categories"]
        for t in c["tabs"]
        for b in t["buttons"]
    }


@pytest.mark.asyncio
async def test_button_price_and_name_are_never_stored(http_client, admin_header):
    """A button's unitPrice and description come from the item master on /detail.

    The request schema offered them as writable, PUT stored them with a raw
    $set, and every route but /detail returned them as read, so a price nobody
    set in the item master could reach the till. They are now ignored on
    write, null on every route but /detail, and null on /detail for a button
    whose item is not in the item master (rather than the string "not found").
    """
    tenant_id = os.environ.get("TENANT_ID")
    await _ensure_tenant(http_client, admin_header, tenant_id)

    item_code = "IBDISP-01"
    missing_code = "IBDISP-MISSING"
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/items",
        json={
            "itemCode": item_code, "description": "Real name", "unitPrice": 100, "unitCost": 50,
            "itemDetails": [], "imageUrls": [], "categoryCode": "001", "taxCode": "01",
        },
        headers=admin_header,
    )
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST), response.text

    def button(code, price, name, pos_x):
        return {
            "posX": pos_x, "posY": 0, "size": "Single", "imageUrl": "", "colorText": "#000",
            "itemCode": code, "unitPrice": price, "description": name,
        }

    def book(*buttons):
        return {
            "title": "Display Only",
            "categories": [{
                "categoryNumber": 1, "title": "c", "color": "#fff",
                "tabs": [{"tabNumber": 1, "title": "t", "color": "#fff", "buttons": list(buttons)}],
            }],
        }

    base = f"/api/v1/tenants/{tenant_id}/item_books"

    # Create: the values sent are not echoed back as if stored.
    response = await http_client.post(base, json=book(button(item_code, 9999, "sent on create", 0)), headers=admin_header)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    item_book_id = response.json()["data"]["itemBookId"]
    assert _buttons(response) == {item_code: (None, None)}

    # PUT the whole book back with values, the way a client edits a /detail read.
    response = await http_client.put(
        f"{base}/{item_book_id}",
        json=book(button(item_code, 1, "sent on put", 0), button(missing_code, 5, "ghost", 1)),
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert _buttons(response) == {item_code: (None, None), missing_code: (None, None)}

    # Adding a button with values does not store them either.
    response = await http_client.post(
        f"{base}/{item_book_id}/categories/1/tabs/1/buttons",
        json=button(item_code, 7, "sent on add", 2),
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    expected = {item_code: (None, None), missing_code: (None, None)}
    response = await http_client.get(f"{base}/{item_book_id}", headers=admin_header)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert _buttons(response) == expected

    response = await http_client.get(base, params={"limit": 100}, headers=admin_header)
    assert response.status_code == status.HTTP_200_OK, response.text
    ours = [b for b in response.json()["data"] if b["itemBookId"] == item_book_id]
    assert len(ours) == 1
    assert {
        btn["itemCode"]: (btn["unitPrice"], btn["description"])
        for c in ours[0]["categories"] for t in c["tabs"] for btn in t["buttons"]
    } == expected

    # /detail resolves from the item master; a code not in it gets nothing.
    response = await http_client.get(f"{base}/{item_book_id}/detail", params={"store_code": "IBDISP"}, headers=admin_header)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert _buttons(response) == {item_code: (100, "Real name"), missing_code: (None, None)}

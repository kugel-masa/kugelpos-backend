"""Writes inside a deleted record are refused and leave it unchanged (issue #324).

Payment variants and the categories, tabs and buttons of an item book live
inside their parent's document. Once the parent is logically deleted, adding,
changing or removing them answers 404 and writes nothing. Inside a live item
book, removing an element stays physical.
"""

import os
import uuid

import pytest

from kugel_common.database import database as db_helper

from tests.integration.logical_delete_masters import base

pytestmark = pytest.mark.asyncio


async def _db():
    return await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")


async def _payment_with_variant(http_client, header) -> str:
    code = f"P{uuid.uuid4().hex[:6].upper()}"
    r = await http_client.post(
        f"{base()}/payments",
        json={"paymentCode": code, "description": "Cashless", "limitAmount": 0.0, "canRefund": True,
              "canDepositOver": False, "canChange": False, "isActive": True},
        headers=header,
    )
    assert r.status_code == 201, r.text
    r = await http_client.post(f"{base()}/payments/{code}/variants", json={"variantCode": "VISA", "name": "VISA"}, headers=header)
    assert r.status_code == 201, r.text
    return code


async def _book_with_button(http_client, header) -> str:
    r = await http_client.post(f"{base()}/item_books", json={"title": "Nested", "categories": []}, headers=header)
    assert r.status_code == 201, r.text
    book = r.json()["data"]["itemBookId"]
    r = await http_client.post(
        f"{base()}/item_books/{book}/categories",
        json={"categoryNumber": 1, "title": "food", "color": "0xF0FFFF", "tabs": []},
        headers=header,
    )
    assert r.status_code == 201, r.text
    r = await http_client.post(
        f"{base()}/item_books/{book}/categories/1/tabs",
        json={"tabNumber": 1, "title": "lunch", "color": "0xF0FFFF", "buttons": []},
        headers=header,
    )
    assert r.status_code == 201, r.text
    r = await http_client.post(
        f"{base()}/item_books/{book}/categories/1/tabs/1/buttons",
        json={"pos_x": 0, "pos_y": 0, "size": "Single", "imageUrl": "u", "colorText": "0xF0FFFF", "itemCode": "49-01"},
        headers=header,
    )
    assert r.status_code == 201, r.text
    return book


async def test_a_deleted_payment_method_takes_no_variant_writes(http_client, admin_header):
    code = await _payment_with_variant(http_client, admin_header)
    assert (await http_client.delete(f"{base()}/payments/{code}", headers=admin_header)).status_code == 200
    before = await (await _db())["master_payment"].find_one({"payment_code": code})

    added = await http_client.post(
        f"{base()}/payments/{code}/variants", json={"variantCode": "JCB", "name": "JCB"}, headers=admin_header
    )
    changed = await http_client.put(
        f"{base()}/payments/{code}/variants/VISA", json={"name": "Visa", "isActive": False}, headers=admin_header
    )
    listed = await http_client.get(f"{base()}/payments/{code}/variants", headers=admin_header)
    single = await http_client.get(f"{base()}/payments/{code}/variants/VISA", headers=admin_header)

    assert [added.status_code, changed.status_code, listed.status_code, single.status_code] == [404, 404, 404, 404]
    after = await (await _db())["master_payment"].find_one({"payment_code": code})
    assert after["variants"] == before["variants"]
    assert after.get("updated_at") == before.get("updated_at")


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "/categories", {"categoryNumber": 2, "title": "drink", "color": "0xF0FFFF", "tabs": []}),
        ("put", "/categories/1", {"categoryNumber": 1, "title": "renamed", "color": "0xF0FFFF", "tabs": []}),
        ("delete", "/categories/1", None),
        ("post", "/categories/1/tabs", {"tabNumber": 2, "title": "dinner", "color": "0xF0FFFF", "buttons": []}),
        ("put", "/categories/1/tabs/1", {"tabNumber": 1, "title": "renamed", "color": "0xF0FFFF", "buttons": []}),
        ("delete", "/categories/1/tabs/1", None),
        ("post", "/categories/1/tabs/1/buttons",
         {"pos_x": 1, "pos_y": 0, "size": "Single", "imageUrl": "u", "colorText": "0xF0FFFF", "itemCode": "49-01"}),
        ("put", "/categories/1/tabs/1/buttons/pos_x/0/pos_y/0",
         {"pos_x": 0, "pos_y": 0, "size": "Single", "imageUrl": "u", "colorText": "0x000000", "itemCode": "49-01"}),
        ("delete", "/categories/1/tabs/1/buttons/pos_x/0/pos_y/0", None),
        ("get", "/detail", None),
    ],
)
async def test_a_deleted_item_book_takes_no_nested_writes(http_client, admin_header, method, path, body):
    book = await _book_with_button(http_client, admin_header)
    assert (await http_client.delete(f"{base()}/item_books/{book}", headers=admin_header)).status_code == 200
    before = await (await _db())["master_item_book"].find_one({"item_book_id": book})

    kwargs = {"headers": admin_header}
    if body is not None:
        kwargs["json"] = body
    if path == "/detail":
        kwargs["params"] = {"store_code": "5678"}
    r = await getattr(http_client, method)(f"{base()}/item_books/{book}{path}", **kwargs)

    assert r.status_code == 404, r.text
    after = await (await _db())["master_item_book"].find_one({"item_book_id": book})
    assert after["categories"] == before["categories"]
    assert after.get("updated_at") == before.get("updated_at")


async def test_removing_an_element_of_a_live_item_book_stays_physical(http_client, admin_header):
    book = await _book_with_button(http_client, admin_header)

    r = await http_client.delete(f"{base()}/item_books/{book}/categories/1/tabs/1/buttons/pos_x/0/pos_y/0", headers=admin_header)

    assert r.status_code == 200, r.text
    got = await http_client.get(f"{base()}/item_books/{book}", params={"include_deleted": "true"}, headers=admin_header)
    assert got.json()["data"]["categories"][0]["tabs"][0]["buttons"] == []

"""An update that loses a race with a delete answers 404 and writes nothing (issue #324).

The service looks the record up, then writes. A delete landing in between must
not be written over: the write's filter carries the live condition, so it
matches nothing and the caller gets 404, not a 500.

The race is staged by deleting the record right after the service's lookup.
"""

import os
import uuid

import pytest

from kugel_common.database import database as db_helper

from tests.integration.logical_delete_masters import base

pytestmark = pytest.mark.asyncio


async def _db():
    return await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")


def _delete_after_lookup(monkeypatch, repo_cls, getter: str, collection: str, key_field: str):
    """Let the service's lookup succeed, then mark the record deleted before its write."""
    original = getattr(repo_cls, getter)

    async def lookup_then_delete(self, code, *args, **kwargs):
        found = await original(self, code, *args, **kwargs)
        if found is not None and not kwargs.get("include_deleted") and not (args and args[0]):
            db = await _db()
            await db[collection].update_one({key_field: code}, {"$set": {"is_deleted": True}})
            monkeypatch.setattr(repo_cls, getter, original)
        return found

    monkeypatch.setattr(repo_cls, getter, lookup_then_delete)


async def test_a_category_update_racing_a_delete(http_client, admin_header, monkeypatch):
    from app.models.repositories.category_master_repository import CategoryMasterRepository

    code = f"R{uuid.uuid4().hex[:6].upper()}"
    body = {"categoryCode": code, "description": "Old", "descriptionShort": "Old", "taxCode": "01"}
    assert (await http_client.post(f"{base()}/categories", json=body, headers=admin_header)).status_code == 201
    _delete_after_lookup(monkeypatch, CategoryMasterRepository, "get_category_by_code_async", "master_category", "category_code")

    r = await http_client.put(f"{base()}/categories/{code}", json={**body, "description": "New"}, headers=admin_header)

    assert r.status_code == 404, r.text
    stored = await (await _db())["master_category"].find_one({"category_code": code})
    assert stored["description"] == "Old"
    assert stored["is_deleted"] is True


async def test_a_payment_variant_change_racing_a_delete(http_client, admin_header):
    code = f"R{uuid.uuid4().hex[:6].upper()}"
    r = await http_client.post(
        f"{base()}/payments",
        json={"paymentCode": code, "description": "Cashless", "limitAmount": 0.0, "canRefund": True,
              "canDepositOver": False, "canChange": False, "isActive": True},
        headers=admin_header,
    )
    assert r.status_code == 201, r.text
    assert (await http_client.post(f"{base()}/payments/{code}/variants", json={"variantCode": "VISA", "name": "VISA"},
                                   headers=admin_header)).status_code == 201
    # The variant write goes first and looks the payment up afterwards, so a
    # delete before the request is the race: the write must not land
    await (await _db())["master_payment"].update_one({"payment_code": code}, {"$set": {"is_deleted": True}})

    r = await http_client.put(f"{base()}/payments/{code}/variants/VISA", json={"name": "Visa", "isActive": False},
                              headers=admin_header)

    assert r.status_code == 404, r.text
    stored = await (await _db())["master_payment"].find_one({"payment_code": code})
    assert stored["variants"][0]["name"] == "VISA"
    assert stored["variants"][0]["is_active"] is True


async def test_an_item_book_nested_write_racing_a_delete(http_client, admin_header, monkeypatch):
    from app.models.repositories.item_book_master_repository import ItemBookMasterRepository

    r = await http_client.post(f"{base()}/item_books", json={"title": "Race", "categories": []}, headers=admin_header)
    assert r.status_code == 201, r.text
    book = r.json()["data"]["itemBookId"]
    _delete_after_lookup(monkeypatch, ItemBookMasterRepository, "get_item_book_async", "master_item_book", "item_book_id")

    r = await http_client.post(
        f"{base()}/item_books/{book}/categories",
        json={"categoryNumber": 1, "title": "food", "color": "0xF0FFFF", "tabs": []},
        headers=admin_header,
    )

    assert r.status_code == 404, r.text
    stored = await (await _db())["master_item_book"].find_one({"item_book_id": book})
    assert stored["categories"] == []

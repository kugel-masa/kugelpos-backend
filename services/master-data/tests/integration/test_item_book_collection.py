# Copyright 2026 masa@kugel
"""Item books live in master_item_book, against a real database.

They used to be written to master_key_preset while the tenant setup built
master_item_book and its unique index, so the index guarded an empty collection.
These tests check where a created item book lands, that the unique index now
covers it, and that the tenant setup carries item books left in the old
collection across.
"""

import os
from datetime import datetime

import pytest
from fastapi import status
from pymongo.errors import DuplicateKeyError

from app.database import database_setup

pytestmark = pytest.mark.asyncio

LEGACY = "master_key_preset"
TARGET = "master_item_book"


async def _db():
    from kugel_common.database import database as db_helper

    return await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")


def _legacy_book(item_book_id: str) -> dict:
    return {
        "tenant_id": os.environ.get("TENANT_ID"),
        "item_book_id": item_book_id,
        "title": f"legacy {item_book_id}",
        "categories": [],
        # Stamped by the repository; the response renders entry_datetime from it.
        "created_at": datetime(2026, 1, 1),
    }


async def test_a_created_item_book_lands_in_master_item_book(http_client, admin_header):
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/item_books",
        json={"title": "collection check", "categories": []},
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    item_book_id = response.json()["data"]["itemBookId"]

    db = await _db()
    assert await db[TARGET].find_one({"item_book_id": item_book_id}) is not None
    assert LEGACY not in await db.list_collection_names()


async def test_the_unique_index_refuses_a_second_book_with_the_same_id():
    db = await _db()
    await db[TARGET].insert_one(_legacy_book("UNIQ-0001"))
    try:
        with pytest.raises(DuplicateKeyError):
            await db[TARGET].insert_one(_legacy_book("UNIQ-0001"))
    finally:
        await db[TARGET].delete_many({"item_book_id": "UNIQ-0001"})


async def test_tenant_setup_moves_books_left_in_the_old_collection(http_client, admin_header):
    db = await _db()
    await db[LEGACY].insert_many([_legacy_book("MOVE-0001"), _legacy_book("MOVE-0002")])
    try:
        await database_setup.move_legacy_item_books(os.environ.get("TENANT_ID"))

        moved = {doc["item_book_id"] async for doc in db[TARGET].find({"item_book_id": {"$regex": "^MOVE-"}})}
        assert moved == {"MOVE-0001", "MOVE-0002"}
        assert await db[LEGACY].count_documents({}) == 0

        # And it is readable through the API again.
        tenant_id = os.environ.get("TENANT_ID")
        response = await http_client.get(f"/api/v1/tenants/{tenant_id}/item_books/MOVE-0001", headers=admin_header)
        assert response.status_code == status.HTTP_200_OK, response.text
    finally:
        await db[LEGACY].drop()
        await db[TARGET].delete_many({"item_book_id": {"$regex": "^MOVE-"}})


async def test_running_the_move_twice_is_harmless():
    db = await _db()
    await db[LEGACY].insert_one(_legacy_book("TWICE-0001"))
    try:
        await database_setup.move_legacy_item_books(os.environ.get("TENANT_ID"))
        await database_setup.move_legacy_item_books(os.environ.get("TENANT_ID"))

        assert await db[TARGET].count_documents({"item_book_id": "TWICE-0001"}) == 1
    finally:
        await db[LEGACY].drop()
        await db[TARGET].delete_many({"item_book_id": "TWICE-0001"})


async def test_a_book_that_differs_between_the_collections_is_kept_in_both():
    db = await _db()
    await db[TARGET].insert_one(_legacy_book("BOTH-0001"))
    await db[LEGACY].insert_one(_legacy_book("BOTH-0001"))
    try:
        await database_setup.move_legacy_item_books(os.environ.get("TENANT_ID"))

        assert await db[LEGACY].count_documents({"item_book_id": "BOTH-0001"}) == 1
        assert await db[TARGET].count_documents({"item_book_id": "BOTH-0001"}) == 1
    finally:
        await db[LEGACY].drop()
        await db[TARGET].delete_many({"item_book_id": "BOTH-0001"})


async def test_a_book_already_copied_is_removed_from_the_old_collection():
    """A run that stopped between the copy and the delete is finished by the next."""
    db = await _db()
    doc = _legacy_book("HALF-0001")
    await db[LEGACY].insert_one(doc)
    await db[TARGET].insert_one(doc)
    try:
        await database_setup.move_legacy_item_books(os.environ.get("TENANT_ID"))

        assert await db[LEGACY].count_documents({}) == 0
        assert await db[TARGET].count_documents({"item_book_id": "HALF-0001"}) == 1
    finally:
        await db[LEGACY].drop()
        await db[TARGET].delete_many({"item_book_id": "HALF-0001"})


async def test_a_book_changed_after_it_was_copied_stays_for_the_next_run():
    """An earlier-version instance still writing to the old collection loses nothing."""
    db = await _db()
    copied = _legacy_book("LATE-0001")
    await db[TARGET].insert_one(copied)
    changed = dict(copied, title="changed later")
    await db[LEGACY].insert_one(changed)
    try:
        await database_setup.move_legacy_item_books(os.environ.get("TENANT_ID"))

        assert await db[LEGACY].find_one({"_id": changed["_id"]}) is not None
    finally:
        await db[LEGACY].drop()
        await db[TARGET].delete_many({"item_book_id": "LATE-0001"})

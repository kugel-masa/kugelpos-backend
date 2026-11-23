"""Creating a logically deleted code restores it (issue #324, US2).

The record comes back with the request's values only, live, stamped for the
tenant like a new record. Item books are excepted: their ids are generated, and
a deleted id is never reused.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

from kugel_common.database import database as db_helper

from tests.integration.logical_delete_masters import MASTERS, RESTORABLE, base, create, list_codes, master_ids

pytestmark = pytest.mark.asyncio


async def _delete(http_client, header, master, code):
    r = await http_client.delete(master.item_path(code), headers=header)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("master", RESTORABLE, ids=master_ids(RESTORABLE))
async def test_creating_a_deleted_code_restores_it_with_the_new_values(http_client, admin_header, master):
    code, r = await create(http_client, admin_header, master, label="Old")
    assert r.status_code == 201, r.text
    await _delete(http_client, admin_header, master, code)
    # Stored times come back as naive UTC, like every record's entryDatetime
    started = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)

    code, r = await create(http_client, admin_header, master, code=code, label="Brand new")

    assert r.status_code == 201, r.text
    got = await http_client.get(master.item_path(code), headers=admin_header)
    assert got.status_code == 200, got.text
    data = got.json()["data"]
    assert data["isDeleted"] is False
    expected = master.create_body(code, "Brand new")[master.label_field]
    assert data[master.label_field] == expected
    assert data["entryDatetime"] is not None
    assert data["lastUpdateDatetime"] is None, "a restored record looks like a newly created one"
    assert datetime.strptime(data["entryDatetime"], "%Y-%m-%d %H:%M:%S") >= started.replace(microsecond=0)
    listed = await http_client.get(master.list_path(), params=master.list_params, headers=admin_header)
    assert code in list_codes(listed, master)

    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    stored = await db[master.collection].find_one({master.key_field: code, "tenant_id": os.environ.get("TENANT_ID")})
    assert stored is not None, "the restored record lost its tenant"
    assert stored.get("shard_key"), "the restored record lost its shard key"
    assert stored.get("created_at") is not None
    if master.name == "item_store":
        assert stored.get("store_code")


async def test_a_restored_record_keeps_none_of_the_old_values(http_client, admin_header):
    code = f"LD{os.urandom(4).hex().upper()}"
    r = await http_client.post(
        f"{base()}/settings",
        json={"name": code, "defaultValue": "old", "values": [{"storeCode": "5678", "value": "store override"}]},
        headers=admin_header,
    )
    assert r.status_code == 201, r.text
    assert (await http_client.delete(f"{base()}/settings/{code}", headers=admin_header)).status_code == 200

    r = await http_client.post(f"{base()}/settings", json={"name": code, "defaultValue": "new", "values": []}, headers=admin_header)

    assert r.status_code == 201, r.text
    data = (await http_client.get(f"{base()}/settings/{code}", headers=admin_header)).json()["data"]
    assert data["defaultValue"] == "new"
    assert data["values"] == []


@pytest.mark.parametrize("master", RESTORABLE, ids=master_ids(RESTORABLE))
async def test_creating_a_live_code_is_still_refused(http_client, admin_header, master):
    code, r = await create(http_client, admin_header, master)
    assert r.status_code == 201, r.text

    _, r = await create(http_client, admin_header, master, code=code)

    assert r.status_code == 400, r.text


@pytest.mark.parametrize("master", RESTORABLE, ids=master_ids(RESTORABLE))
@pytest.mark.parametrize("deleted_first", [True, False], ids=["restore", "new"])
async def test_concurrent_creates_never_answer_500(http_client, admin_header, master, deleted_first):
    code, r = await create(http_client, admin_header, master)
    assert r.status_code == 201, r.text
    if deleted_first:
        await _delete(http_client, admin_header, master, code)
    else:
        r = await http_client.delete(master.item_path(code), params={"is_logical": "false"}, headers=admin_header)
        assert r.status_code == 200, r.text

    results = await asyncio.gather(
        *[create(http_client, admin_header, master, code=code, label=f"Race {i}") for i in range(2)]
    )

    statuses = sorted(r.status_code for _, r in results)
    assert statuses == [201, 400], [r.text for _, r in results]


async def test_a_deleted_item_book_id_is_never_reused(http_client, admin_header):
    book = next(m for m in MASTERS if m.name == "item_book")
    first, r = await create(http_client, admin_header, book)
    assert r.status_code == 201, r.text
    await _delete(http_client, admin_header, book, first)

    second, r = await create(http_client, admin_header, book)

    assert r.status_code == 201, r.text
    assert second != first
    old = await http_client.get(book.item_path(first), params={"include_deleted": "true"}, headers=admin_header)
    assert old.status_code == 200, old.text
    assert old.json()["data"]["isDeleted"] is True

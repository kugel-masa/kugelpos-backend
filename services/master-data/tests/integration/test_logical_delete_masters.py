"""Every deletable master deletes logically by default (issue #324, US1 / US3).

A deleted record leaves the default reads, lists and counts, shows up with
include_deleted=true, and refuses updates and a second logical delete. A
physical delete removes it, deleted or not. A record without the field is live.
"""

import os

import pytest

from kugel_common.database import database as db_helper

from tests.integration.logical_delete_masters import MASTERS, create, list_codes, master_ids

pytestmark = pytest.mark.asyncio


async def _total(http_client, header, master, include_deleted=False):
    r = await http_client.get(
        master.list_path(), params={**master.list_params, "include_deleted": str(include_deleted).lower()}, headers=header
    )
    assert r.status_code == 200, r.text
    return r


@pytest.mark.parametrize("master", MASTERS, ids=master_ids(MASTERS))
async def test_a_delete_is_logical_by_default(http_client, admin_header, master):
    code, r = await create(http_client, admin_header, master)
    assert r.status_code == 201, r.text
    before = (await _total(http_client, admin_header, master)).json()["metadata"]["total"]

    r = await http_client.delete(master.item_path(code), headers=admin_header)
    assert r.status_code == 200, r.text

    r = await http_client.get(master.item_path(code), headers=admin_header)
    assert r.status_code == 404, r.text

    listed = await _total(http_client, admin_header, master)
    assert code not in list_codes(listed, master)
    assert listed.json()["metadata"]["total"] == before - 1

    r = await http_client.get(master.item_path(code), params={"include_deleted": "true"}, headers=admin_header)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["isDeleted"] is True

    listed = await _total(http_client, admin_header, master, include_deleted=True)
    rows = {row[master.code_field]: row for row in listed.json()["data"]}
    assert rows[code]["isDeleted"] is True

    r = await http_client.put(master.item_path(code), json=master.update_body(code, "New"), headers=admin_header)
    assert r.status_code == 404, r.text

    r = await http_client.delete(master.item_path(code), headers=admin_header)
    assert r.status_code == 404, r.text


@pytest.mark.parametrize("master", MASTERS, ids=master_ids(MASTERS))
async def test_a_live_record_answers_is_deleted_false(http_client, admin_header, master):
    code, r = await create(http_client, admin_header, master)
    assert r.status_code == 201, r.text

    r = await http_client.get(master.item_path(code), headers=admin_header)

    assert r.status_code == 200, r.text
    assert r.json()["data"]["isDeleted"] is False


@pytest.mark.parametrize("master", MASTERS, ids=master_ids(MASTERS))
async def test_a_record_without_the_field_is_live(http_client, admin_header, master):
    code, r = await create(http_client, admin_header, master)
    assert r.status_code == 201, r.text
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    unset = await db[master.collection].update_one({master.key_field: code}, {"$unset": {"is_deleted": ""}})
    assert unset.matched_count == 1

    r = await http_client.get(master.item_path(code), headers=admin_header)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["isDeleted"] is False
    assert code in list_codes(await _total(http_client, admin_header, master), master)


@pytest.mark.parametrize("master", MASTERS, ids=master_ids(MASTERS))
@pytest.mark.parametrize("deleted_first", [False, True], ids=["live", "logically-deleted"])
async def test_a_physical_delete_removes_the_record(http_client, admin_header, master, deleted_first):
    code, r = await create(http_client, admin_header, master)
    assert r.status_code == 201, r.text
    if deleted_first:
        assert (await http_client.delete(master.item_path(code), headers=admin_header)).status_code == 200

    r = await http_client.delete(master.item_path(code), params={"is_logical": "false"}, headers=admin_header)
    assert r.status_code == 200, r.text

    r = await http_client.get(master.item_path(code), params={"include_deleted": "true"}, headers=admin_header)
    assert r.status_code == 404, r.text


@pytest.mark.parametrize("master", MASTERS, ids=master_ids(MASTERS))
@pytest.mark.parametrize("is_logical", ["true", "false"])
async def test_deleting_an_unknown_code_is_not_found(http_client, admin_header, master, is_logical):
    r = await http_client.delete(master.item_path(master.new_code()), params={"is_logical": is_logical}, headers=admin_header)

    assert r.status_code == 404, r.text


@pytest.mark.parametrize("flag", ["is_logical_deleted", "include_deleted"])
async def test_the_item_alias_finds_live_and_deleted_items(http_client, admin_header, flag):
    """Issue #324: is_logical_deleted is a deprecated alias of include_deleted.

    Before #324 it was an exact match: true found deleted items only.
    """
    item = next(m for m in MASTERS if m.name == "item_common")
    live, _ = await create(http_client, admin_header, item)
    deleted, _ = await create(http_client, admin_header, item)
    assert (await http_client.delete(item.item_path(deleted), headers=admin_header)).status_code == 200

    for code, expected in ((live, False), (deleted, True)):
        r = await http_client.get(item.item_path(code), params={flag: "true"}, headers=admin_header)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["isDeleted"] is expected

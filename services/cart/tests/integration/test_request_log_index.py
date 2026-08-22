# Copyright 2026 masa@kugel
"""The request-log index, and what it used to constrain (issue #182).

The index was written for per-terminal separation and keyed on `store_code` and
`terminal_no` at the top level — where a request log document does not have them;
they live under `terminal_info`. Missing fields index as null, so it resolved to
`(tenant_id, null, null, accept_time)` and enforced *one request per tenant per
timestamp*, across every terminal in that tenant. It has never done the job it
was given.

It is also no longer unique. What a unique index here could protect against — the
same request written twice — does not happen: `insert_many` stamps `_id` into the
documents in place, so a retried batch is refused by `_id` (issue #183). What it
did do was reject audit records that legitimately happened, silently.

Here rather than in `services/commons` because the subject is the collection: the
keys the index actually resolves to, and whether MongoDB accepts the rows.
"""

import os
import uuid

import pytest
import pytest_asyncio
from kugel_common.database import database as db_helper

from app.database import database_setup

pytestmark = pytest.mark.asyncio

STALE_KEYS = ("tenant_id", "store_code", "terminal_no", "request_info.accept_time")
WANTED_KEYS = (
    "tenant_id",
    "terminal_info.store_code",
    "terminal_info.terminal_no",
    "request_info.accept_time",
)


def _row(store_code, terminal_no, accept_time):
    """A request log row, shaped the way the middleware writes one."""
    return {
        "tenant_id": os.environ.get("TENANT_ID"),
        "client_info": {"ip_address": "127.0.0.1"},
        "request_info": {"method": "POST", "url": "/probe", "body": None, "accept_time": accept_time},
        "response_info": {"status_code": 200, "process_time_ms": 1, "body": None},
        "terminal_info": {
            "tenant_id": os.environ.get("TENANT_ID"),
            "store_code": store_code,
            "terminal_no": terminal_no,
            "business_date": "20260822",
            "open_counter": 1,
        },
    }


async def _indexes(collection):
    info = await collection.index_information()
    return {name: (tuple(k for k, _ in i["key"]), bool(i.get("unique"))) for name, i in info.items() if name != "_id_"}


@pytest_asyncio.fixture
async def request_log():
    """The tenant's request-log collection, restored afterwards."""
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    collection = db[os.environ.get("DB_COLLECTION_NAME_REQUEST_LOG", "log_request")]
    yield collection
    await collection.delete_many({"request_info.url": "/probe"})
    await database_setup.create_request_log_collection(os.environ.get("TENANT_ID"))


class TestTheIndexThisCollectionGets:
    async def test_it_is_keyed_on_the_paths_that_exist(self, request_log):
        await database_setup.create_request_log_collection(os.environ.get("TENANT_ID"))

        keys = {k for k, _ in (await _indexes(request_log)).values()}

        assert WANTED_KEYS in keys, f"the corrected index is not there: {keys}"
        assert STALE_KEYS not in keys, "the index keyed on fields that do not exist is still there"

    async def test_it_is_not_unique(self, request_log):
        await database_setup.create_request_log_collection(os.environ.get("TENANT_ID"))

        unique = {k: u for k, u in (await _indexes(request_log)).values()}

        assert unique[WANTED_KEYS] is False


class TestWhatTheCollectionNowAccepts:
    async def test_two_terminals_at_the_same_instant_are_both_kept(self, request_log):
        # The record this collection exists to hold. Under the old index these
        # collided on (tenant, null, null, accept_time) and one was refused - an
        # audit row for a request that happened, dropped because another terminal
        # was busy at the same microsecond.
        await database_setup.create_request_log_collection(os.environ.get("TENANT_ID"))
        instant = f"2099-01-01T00:00:00.{uuid.uuid4().hex[:6]}"

        await request_log.insert_many([_row("5678", 9, instant), _row("9999", 1, instant)])

        assert await request_log.count_documents({"request_info.accept_time": instant}) == 2

    async def test_one_terminal_twice_at_the_same_instant_is_also_kept(self, request_log):
        # An audit trail should not be the thing that decides a record did not
        # happen. Rejecting it loses the row; keeping it costs a duplicate that
        # is visible.
        await database_setup.create_request_log_collection(os.environ.get("TENANT_ID"))
        instant = f"2099-01-01T00:00:01.{uuid.uuid4().hex[:6]}"

        await request_log.insert_many([_row("5678", 9, instant), _row("5678", 9, instant)])

        assert await request_log.count_documents({"request_info.accept_time": instant}) == 2


class TestTheMigration:
    async def test_a_collection_carrying_the_old_index_is_moved_over(self, request_log):
        """What an upgraded deployment starts from."""
        await request_log.drop_indexes()
        await request_log.create_index(
            [(k, 1) for k in STALE_KEYS],
            name="log_request_index_tenant_id_store_code_terminal_no_request_info.accept_time",
            unique=True,
        )
        assert STALE_KEYS in {k for k, _ in (await _indexes(request_log)).values()}, "precondition"

        await database_setup.create_request_log_collection(os.environ.get("TENANT_ID"))

        keys = {k for k, _ in (await _indexes(request_log)).values()}
        assert STALE_KEYS not in keys, "the old index survived the migration"
        assert WANTED_KEYS in keys

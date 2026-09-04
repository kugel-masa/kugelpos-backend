# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""What the request-log retention does to a real MongoDB (issue #221).

The unit tests pin the declaration; only a server says whether the declaration
becomes an index that removes anything. Three of the things that made this hard
are invisible without one:

- a TTL never expires a document whose indexed field is missing or is not a date,
  and every request log written before this work carries `created_at: null`
- `createIndexes` refuses to change the options of an index that already exists,
  answering IndexOptionsConflict, which the provisioning swallows with a warning
- `collMod` can change a TTL's retention but cannot turn a plain index into a TTL
  one at all

Each of those fails by looking like success, so each is checked here against what
MongoDB actually holds afterwards.
"""

import os

import pytest
import pytest_asyncio
from bson import ObjectId


COLLECTION = "log_request"


def _db_names():
    from app.config.settings import settings

    tenant = os.environ.get("TENANT_ID")
    return f"{settings.DB_NAME_PREFIX}_{tenant}", f"{settings.DB_NAME_PREFIX}_commons"


@pytest_asyncio.fixture
async def clean_log_request():
    """Drop the collection in both targets, so each test starts from nothing."""
    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    for name in _db_names():
        db = await db_helper.get_db_async(name)
        await db[COLLECTION].drop()
    yield
    for name in _db_names():
        db = await db_helper.get_db_async(name)
        await db[COLLECTION].drop()


async def _indexes(db_name):
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(db_name)
    return await db[COLLECTION].index_information()


def _ttl_of(info):
    return [i.get("expireAfterSeconds") for i in info.values() if "expireAfterSeconds" in i]


@pytest.mark.asyncio
async def test_both_copies_get_the_expiry(clean_log_request):
    """Every record is written to the tenant database AND to commons.

    Provisioning used to reach only the first, so the commons copy took the same
    traffic with no index and no way to shrink.
    """
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    for db_name in _db_names():
        info = await _indexes(db_name)
        assert _ttl_of(info) == [settings.REQUEST_LOG_TTL_SECONDS], f"{db_name}: {info.keys()}"


@pytest.mark.asyncio
async def test_no_database_is_created_for_the_tenant_named_None(clean_log_request):
    """`tenant_id=None` addresses the commons database, not a tenant called "None"."""
    from kugel_common.database import database as db_helper
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    client = await db_helper.get_client_async()
    names = await client.list_database_names()
    assert f"{settings.DB_NAME_PREFIX}_None" not in names, names


@pytest.mark.asyncio
async def test_a_changed_retention_is_applied_to_the_existing_index(clean_log_request, monkeypatch):
    """`createIndexes` will not change it, and the keys-only check calls that success."""
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    tenant = os.environ.get("TENANT_ID")
    monkeypatch.setattr(settings, "REQUEST_LOG_TTL_SECONDS", 3600)
    await create_request_log_collection(tenant_id=tenant)
    assert _ttl_of(await _indexes(_db_names()[0])) == [3600]

    monkeypatch.setattr(settings, "REQUEST_LOG_TTL_SECONDS", 7200)
    await create_request_log_collection(tenant_id=tenant)

    assert _ttl_of(await _indexes(_db_names()[0])) == [7200], "the operator's new retention was ignored"


@pytest.mark.asyncio
async def test_a_plain_index_on_the_same_key_is_rebuilt_with_the_expiry(clean_log_request):
    """An index with the right keys and no expiry is the failure wearing a disguise.

    `collMod` cannot add `expireAfterSeconds` to a plain index, and the ensure
    loop's IndexOptionsConflict is swallowed - so without the rebuild the
    collection reports as expiring while nothing expires.
    """
    from kugel_common.database import database as db_helper
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    db_name = _db_names()[0]
    db = await db_helper.get_db_async(db_name)
    await db[COLLECTION].create_index([("created_at", 1)], name="log_request_index_created_at")
    assert _ttl_of(await _indexes(db_name)) == [], "precondition: a plain index, no expiry"

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    assert _ttl_of(await _indexes(db_name)) == [settings.REQUEST_LOG_TTL_SECONDS]


@pytest.mark.asyncio
async def test_the_rows_written_before_the_date_existed_are_given_one(clean_log_request):
    """A TTL skips a document whose indexed field is not a date.

    Those rows are the reason the index exists - measured downstream at 6.4M
    documents / 23.8 GiB - so an index that cannot see them fixes nothing.
    """
    from kugel_common.database import database as db_helper
    from app.database.database_setup import create_request_log_collection

    db_name = _db_names()[0]
    db = await db_helper.get_db_async(db_name)
    old_id = ObjectId()
    await db[COLLECTION].insert_many(
        [
            {"_id": old_id, "tenant_id": "T", "created_at": None},
            {"tenant_id": "T"},  # the field missing entirely, not merely null
        ]
    )

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    assert await db[COLLECTION].count_documents({"created_at": None}) == 0
    filled = await db[COLLECTION].find_one({"_id": old_id})
    # The date is recovered from the ObjectId, which embeds the second it was made.
    assert filled["created_at"] == old_id.generation_time.replace(tzinfo=filled["created_at"].tzinfo)


@pytest.mark.asyncio
async def test_a_row_that_already_has_a_date_is_left_alone(clean_log_request):
    from datetime import datetime, timezone

    from kugel_common.database import database as db_helper
    from app.database.database_setup import create_request_log_collection

    db_name = _db_names()[0]
    db = await db_helper.get_db_async(db_name)
    stamped = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    await db[COLLECTION].insert_one({"_id": ObjectId(), "created_at": stamped})

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    kept = await db[COLLECTION].find_one({})
    assert kept["created_at"].replace(tzinfo=timezone.utc) == stamped


@pytest.mark.asyncio
async def test_a_constraint_the_declaration_lacks_is_not_silently_dropped(clean_log_request):
    """Adding the expiry means rebuilding, and rebuilding from the declaration
    would drop a `unique` the live index carries. Widening a constraint quietly
    is the failure this whole path exists to prevent, so it stops instead.
    """
    from kugel_common.database import database as db_helper
    # Two classes share this name; the database module raises its own.
    from kugel_common.database.database_exceptions import DatabaseException
    from app.database.database_setup import create_request_log_collection

    db = await db_helper.get_db_async(_db_names()[0])
    await db[COLLECTION].create_index([("created_at", 1)], name="log_request_index_created_at", unique=True)

    with pytest.raises(DatabaseException, match="unique"):
        await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    # And it is left as it was, rather than half-migrated.
    info = await _indexes(_db_names()[0])
    assert info["log_request_index_created_at"].get("unique") is True


@pytest.mark.asyncio
async def test_another_process_getting_there_first_is_not_a_failure(clean_log_request, monkeypatch):
    """Two services provisioning the same collection at once both see the plain
    index; the loser's `drop_index` finds nothing left to drop. What matters is
    the state afterwards, so it is re-read rather than inferred from who raised.

    The other process is simulated by a collection proxy: motor hands back a new
    object for every `db[name]`, so an attribute set on one of them is not the
    one the code under test uses.
    """
    from pymongo.errors import OperationFailure

    from kugel_common.database import database as db_helper
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    db_name = _db_names()[0]
    db = await db_helper.get_db_async(db_name)
    await db[COLLECTION].create_index([("created_at", 1)], name="log_request_index_created_at")

    raced = {"done": False}
    WINNER_TTL = 12345  # what the other process declared

    class _Collection:
        def __init__(self, real):
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        async def drop_index(self, index_name, *args, **kwargs):
            # The winner: drops and rebuilds with the expiry. Then this one's own
            # drop finds nothing, which is what the server answers in the race.
            raced["done"] = True
            await self._real.drop_index(index_name, *args, **kwargs)
            # Deliberately NOT this process's retention: during a rolling
            # update the winner is a different version with a different
            # setting, and accepting an expiry merely because one exists
            # would leave the shortened retention quietly unapplied.
            await self._real.create_index(
                [("created_at", 1)],
                name=index_name,
                expireAfterSeconds=WINNER_TTL,
            )
            raise OperationFailure(f"index not found with name [{index_name}]")

    class _Database:
        def __init__(self, real):
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        def __getitem__(self, name):
            real = self._real[name]
            return _Collection(real) if name == COLLECTION and not raced["done"] else real

    original_get_db = db_helper.get_db_async

    async def _proxied(name):
        real = await original_get_db(name)
        return _Database(real) if name == db_name else real

    monkeypatch.setattr(db_helper, "get_db_async", _proxied)

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    assert raced["done"], "the race was never reached"
    monkeypatch.undo()
    # This process's declaration, not the winner's.
    assert _ttl_of(await _indexes(db_name)) == [settings.REQUEST_LOG_TTL_SECONDS]


@pytest.mark.asyncio
async def test_retention_of_zero_backfills_nothing_either(clean_log_request, monkeypatch):
    """With no expiry declared there is nothing for a date to feed, and walking a
    collection of millions to prepare for an index that is never created is pure
    cost.
    """
    from kugel_common.database import database as db_helper
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    db_name = _db_names()[0]
    db = await db_helper.get_db_async(db_name)
    await db[COLLECTION].insert_one({"_id": ObjectId(), "created_at": None})

    monkeypatch.setattr(settings, "REQUEST_LOG_TTL_SECONDS", 0)
    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    assert await db[COLLECTION].count_documents({"created_at": None}) == 1


@pytest.mark.asyncio
async def test_retention_of_zero_declares_nothing(clean_log_request, monkeypatch):
    """0 has to mean no expiry.

    To MongoDB `expireAfterSeconds: 0` means "expire AT the stored date", which
    would delete each request log as soon as the TTL monitor next ran.
    """
    from app.database.database_setup import create_request_log_collection
    from app.config.settings import settings

    monkeypatch.setattr(settings, "REQUEST_LOG_TTL_SECONDS", 0)

    await create_request_log_collection(tenant_id=os.environ.get("TENANT_ID"))

    for db_name in _db_names():
        assert _ttl_of(await _indexes(db_name)) == [], db_name

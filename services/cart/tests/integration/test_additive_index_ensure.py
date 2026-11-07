# Copyright 2026 masa@kugel
"""The startup self-repair creates what is missing and changes nothing else.

Here rather than in `services/commons` because what matters is what MongoDB ends
up holding: a missing index built, a retired one still standing, a unique index
that cannot be built reported instead of raised - and never a collection left
with no unique index at all.
"""

import logging
import uuid

import pytest
import pytest_asyncio
from kugel_common.database import database as db_helper
from kugel_common.database.database import additive_index_ensure, create_collection_with_indexes_async
from kugel_common.database.database_exceptions import DatabaseException

pytestmark = pytest.mark.asyncio

OLD = {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "transaction_no": 1}
NEW = {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_counter": 1, "transaction_no": 1}
CART = {"tenant_id": 1, "store_code": 1, "cart_id": 1}


def _keys(info):
    return {tuple(i["key"]) for i in info.values()}


@pytest_asyncio.fixture
async def collection():
    db_name = f"db_probe_additive_{uuid.uuid4().hex[:8]}"
    name = "log_tran"
    db = await db_helper.get_db_async(db_name)
    await db.create_collection(name)
    yield db_name, name, db
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)


async def test_a_missing_index_is_created(collection):
    db_name, name, db = collection

    with additive_index_ensure():
        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[
                {"keys": CART, "unique": True, "partialFilterExpression": {"cart_id": {"$type": "string"}}}
            ],
            index_name=f"{name}_index",
        )

    assert tuple(CART.items()) in _keys(await db[name].index_information())


async def test_a_retired_index_is_left_standing(collection, caplog):
    # Dropping it and then failing to build the replacement would leave no unique
    # index at all; startup never takes that chance.
    db_name, name, db = collection
    await db[name].create_index(list(OLD.items()), unique=True, name="old_numbering")

    with additive_index_ensure(), caplog.at_level(logging.WARNING):
        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": NEW, "unique": True}],
            index_name=f"{name}_index",
            drop_indexes_by_keys=[OLD],
        )

    keys = _keys(await db[name].index_information())
    assert tuple(OLD.items()) in keys, "startup dropped an index"
    assert tuple(NEW.items()) in keys
    assert "retired index" in caplog.text


async def test_a_unique_index_blocked_by_duplicates_is_reported_not_raised(collection, caplog):
    db_name, name, db = collection
    doc = {"tenant_id": "T", "store_code": "S", "cart_id": "c1"}
    await db[name].insert_many([dict(doc), dict(doc)])

    with additive_index_ensure(), caplog.at_level(logging.ERROR):
        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": CART, "unique": True}],
            index_name=f"{name}_index",
        )

    assert tuple(CART.items()) not in _keys(await db[name].index_information())
    assert "is missing" in caplog.text
    assert "c1" in caplog.text, "the documents in the way have to be named"
    assert "POST /api/v1/tenants" in caplog.text


async def test_outside_the_context_the_same_gap_still_raises(collection):
    # The tenant API keeps its guarantee: a declared index that cannot be built
    # fails the setup rather than reporting success.
    db_name, name, db = collection
    doc = {"tenant_id": "T", "store_code": "S", "cart_id": "c1"}
    await db[name].insert_many([dict(doc), dict(doc)])

    with pytest.raises(DatabaseException):
        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": CART, "unique": True}],
            index_name=f"{name}_index",
        )


async def test_a_changed_expiry_is_not_applied_at_startup(collection, caplog):
    # collMod / rebuild change an index in place; startup only adds.
    db_name, name, db = collection
    await db[name].create_index([("created_at", 1)], expireAfterSeconds=100, name=f"{name}_index_created_at")

    with additive_index_ensure(), caplog.at_level(logging.ERROR):
        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": {"created_at": 1}, "expireAfterSeconds": 50}],
            index_name=f"{name}_index",
        )

    info = await db[name].index_information()
    assert info[f"{name}_index_created_at"]["expireAfterSeconds"] == 100
    assert "expireAfterSeconds 100 (declared 50)" in caplog.text


async def test_the_whole_cart_setup_runs_additively_over_an_existing_tenant():
    """End to end over cart's own declaration, as startup runs it."""
    from app.config.settings import settings
    from app.database import database_setup

    tenant_id = f"ADD{uuid.uuid4().hex[:6].upper()}"
    db_name = f"{settings.DB_NAME_PREFIX}_{tenant_id}"
    db = await db_helper.get_db_async(db_name)
    # An existing tenant from before #156: log_tran with only its old index.
    await db["log_tran"].create_index(list(OLD.items()), unique=True, name="old_numbering")
    try:
        with additive_index_ensure():
            await database_setup.execute(tenant_id)

        keys = _keys(await db["log_tran"].index_information())
        assert tuple(CART.items()) in keys, "the cart_id index never reached the existing tenant"
        assert tuple(OLD.items()) in keys, "startup dropped an index"
    finally:
        client = await db_helper.get_client_async()
        await client.drop_database(db_name)


@pytest.mark.parametrize(
    "live_options, declared",
    [
        ({"unique": True}, {}),
        ({"partialFilterExpression": {"cart_id": {"$type": "string"}}}, {}),
        ({"expireAfterSeconds": 100}, {}),
    ],
    ids=["unique-dropped", "partial-dropped", "expiry-dropped"],
)
async def test_an_option_the_declaration_dropped_is_reported_too(collection, caplog, live_options, declared):
    # createIndexes refuses to take an option away just as it refuses to add one,
    # so a declaration that dropped one is a pending migration as well.
    db_name, name, db = collection
    await db[name].create_index([("cart_id", 1)], name=f"{name}_index_cart_id", **live_options)

    with additive_index_ensure(), caplog.at_level(logging.ERROR):
        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": {"cart_id": 1}, **declared}],
            index_name=f"{name}_index",
        )

    assert "exists with different options" in caplog.text

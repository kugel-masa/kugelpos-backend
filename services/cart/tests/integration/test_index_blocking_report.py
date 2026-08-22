# Copyright 2026 masa@kugel
"""Naming the data that blocks a unique index (issue #185).

Here rather than in `services/commons` because the answer comes from MongoDB: the
point is which documents are actually in the way, and a mock would only return
what the test put in it.

Collections are created before their indexes, so anything already written has to
satisfy them. When it does not, the index can never be built and tenant setup
fails on every retry — which was reported as `Error creating tenant: T6216` and
nothing else. Observed on real data: a journal held transaction 1 four times.
"""

import uuid

import pytest
import pytest_asyncio
from kugel_common.database import database as db_helper
from kugel_common.database.database import (
    BLOCKING_DUPLICATE_SAMPLE,
    create_collection_with_indexes_async,
    find_blocking_duplicates_async,
)
from kugel_common.database.database_exceptions import DatabaseException

pytestmark = pytest.mark.asyncio

KEYS = {"tenant_id": 1, "store_code": 1, "terminal_no": 1, "business_counter": 1, "transaction_no": 1}


def _tranlog(transaction_no, **over):
    doc = {
        "tenant_id": "T0001",
        "store_code": "5678",
        "terminal_no": 9,
        "business_counter": 1,
        "transaction_no": transaction_no,
    }
    doc.update(over)
    return doc


@pytest_asyncio.fixture
async def collection():
    """A throwaway collection in its own database."""
    db_name = f"db_probe_185_{uuid.uuid4().hex[:8]}"
    name = "log_tran"
    db = await db_helper.get_db_async(db_name)
    yield db_name, name, db
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)


class TestFindingWhatIsInTheWay:
    async def test_the_colliding_key_values_are_reported(self, collection):
        _, name, db = collection
        await db[name].insert_many([_tranlog(1), _tranlog(1), _tranlog(1), _tranlog(2), _tranlog(2), _tranlog(3)])

        found = await find_blocking_duplicates_async(db, name, KEYS)

        counts = {d["n"] for d in found}
        assert counts == {3, 2}, f"expected the 3x and the 2x collision, got {found}"

    async def test_a_collection_with_no_collisions_reports_none(self, collection):
        _, name, db = collection
        await db[name].insert_many([_tranlog(1), _tranlog(2), _tranlog(3)])

        assert await find_blocking_duplicates_async(db, name, KEYS) == []

    async def test_documents_outside_a_partial_filter_are_not_blocking(self, collection):
        # A partial index does not index them, so they cannot be what stops it
        # being built - naming them would send an operator after the wrong rows.
        _, name, db = collection
        await db[name].insert_many(
            [
                _tranlog(1, cart_id="c1"),
                _tranlog(1, cart_id="c1"),  # blocking
                _tranlog(2),  # no cart_id at all - outside the filter
                _tranlog(2),
            ]
        )

        found = await find_blocking_duplicates_async(
            db, name, KEYS, partial_filter_expression={"cart_id": {"$type": "string"}}
        )

        assert len(found) == 1, f"documents outside the partial filter were reported: {found}"
        assert found[0]["n"] == 2

    async def test_the_sample_is_bounded(self, collection):
        _, name, db = collection
        await db[name].insert_many([_tranlog(n) for n in range(40) for _ in range(2)])

        found = await find_blocking_duplicates_async(db, name, KEYS)

        assert len(found) == BLOCKING_DUPLICATE_SAMPLE


class TestWhatTheSetupSays:
    async def test_the_failure_names_the_collection_and_the_documents(self, collection):
        db_name, name, db = collection
        await db[name].insert_many([_tranlog(1), _tranlog(1), _tranlog(1)])

        with pytest.raises(DatabaseException) as caught:
            await create_collection_with_indexes_async(
                db_name=db_name,
                collection_name=name,
                index_keys_list=[{"keys": KEYS, "unique": True}],
                index_name="probe_index",
            )

        message = str(caught.value)
        assert name in message, "the failure did not name the collection"
        assert "x3" in message, "the failure did not say how many documents collide"
        assert "transaction_no" in message and "T0001" in message, (
            f"the failure did not name the colliding key values: {message}"
        )

    async def test_a_collection_that_can_be_indexed_succeeds(self, collection):
        db_name, name, db = collection
        await db[name].insert_many([_tranlog(1), _tranlog(2)])

        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": KEYS, "unique": True}],
            index_name="probe_index",
        )

        present = [tuple(tuple(k) for k in i["key"]) for i in (await db[name].index_information()).values()]
        assert tuple(KEYS.items()) in present


class TestAnIndexWithTheRightKeysAndTheWrongOptions:
    async def test_a_non_unique_index_on_the_required_keys_is_reported(self, collection):
        """The same failure wearing a disguise.

        `createIndexes` will not change an existing index's options - it refuses
        with IndexOptionsConflict, which the ensure loop logs as a warning. A
        check that only compares keys then reports success over a uniqueness
        constraint that is not being enforced: exactly the fail-open this
        verification exists to close.
        """
        db_name, name, db = collection
        # Both halves are needed for the fail-open: the duplicates stop the unique
        # index being built, and the non-unique index leaves the keys present so a
        # keys-only check finds nothing wrong. MongoDB lets the two coexist under
        # different names, so this is not hypothetical.
        await db[name].insert_many([_tranlog(1), _tranlog(1), _tranlog(2)])
        await db[name].create_index(list(KEYS.items()), name="already_here", unique=False)

        with pytest.raises(DatabaseException) as caught:
            await create_collection_with_indexes_async(
                db_name=db_name,
                collection_name=name,
                index_keys_list=[{"keys": KEYS, "unique": True}],
                index_name="probe_index",
            )

        message = str(caught.value)
        assert "is unique" in message, f"the mismatch was not reported: {message}"
        assert "x2" in message, "the failure did not say what is keeping it non-unique"
        assert name in message

    async def test_a_non_unique_index_is_fine_when_none_was_required(self, collection):
        db_name, name, db = collection
        await db[name].create_index(list(KEYS.items()), name="already_here", unique=False)

        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": KEYS}],
            index_name="probe_index",
        )

    async def test_a_unique_index_is_found_whatever_order_it_is_listed_in(self, collection):
        """MongoDB lets a unique and a non-unique index share a key pattern.

        Both are then reported for the same keys, so a check that keeps only one
        of them decides by listing order - and fails a collection whose
        constraint is present and enforced.
        """
        db_name, name, db = collection
        await db[name].insert_many([_tranlog(1), _tranlog(2)])
        await db[name].create_index(list(KEYS.items()), name="the_unique_one", unique=True)
        await db[name].create_index(list(KEYS.items()), name="listed_after_it", unique=False)

        await create_collection_with_indexes_async(
            db_name=db_name,
            collection_name=name,
            index_keys_list=[{"keys": KEYS, "unique": True}],
            index_name="probe_index",
        )

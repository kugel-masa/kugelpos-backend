# Copyright 2026 masa@kugel
"""Aggregation returns the same results after the driver change (#301, C-5).

Under the PyMongo async API `aggregate()` is a coroutine that returns the
cursor, not the cursor itself. A missing `await` is caught by the
callers' broad `except` and turns into an empty result, so these tests check
the rows themselves, not only that nothing raised.
"""
import pytest

from kugel_common.database.database import find_blocking_duplicates_async

from ._repository import SampleDocument, make_repository


@pytest.mark.asyncio
async def test_execute_pipeline_returns_grouped_rows(test_db):
    repo = await make_repository(test_db)
    for key, group, amount in [("a", "x", 100), ("b", "x", 50), ("c", "y", 7)]:
        assert await repo.create_async(SampleDocument(key=key, group=group, amount=amount))

    rows = await repo.execute_pipeline(
        [
            {"$group": {"_id": "$group", "total": {"$sum": "$amount"}, "n": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
    )

    assert rows == [
        {"_id": "x", "total": 150, "n": 2},
        {"_id": "y", "total": 7, "n": 1},
    ]


@pytest.mark.asyncio
async def test_execute_pipeline_on_empty_collection_returns_empty_list(test_db):
    repo = await make_repository(test_db)
    assert await repo.execute_pipeline([{"$match": {"key": "none"}}]) == []


@pytest.mark.asyncio
async def test_find_blocking_duplicates_names_the_colliding_values(test_db):
    await test_db["dup"].insert_many(
        [{"code": "A"}, {"code": "A"}, {"code": "A"}, {"code": "B"}, {"code": "B"}, {"code": "C"}]
    )

    rows = await find_blocking_duplicates_async(test_db, "dup", {"code": 1})

    assert rows == [{"_id": {"code": "A"}, "n": 3}, {"_id": {"code": "B"}, "n": 2}]


@pytest.mark.asyncio
async def test_find_blocking_duplicates_respects_the_limit(test_db):
    await test_db["dup"].insert_many([{"code": c} for c in "AABBCC"])

    rows = await find_blocking_duplicates_async(test_db, "dup", {"code": 1}, limit=2)

    assert len(rows) == 2

# Copyright 2026 masa@kugel
"""`max=0` still means "no limit" (#301, FR-004, C-4).

The PyMongo async cursor refuses `to_list(0)` with ValueError (the previous
driver returned an empty list). The repository's own `max=0` means "no limit"
and is mapped to an unlimited fetch before it reaches the cursor; these tests
pin both halves.
"""
import pytest

from ._repository import SampleDocument, make_repository


async def _three_documents(db):
    repo = await make_repository(db)
    for key in ("a", "b", "c"):
        assert await repo.create_async(SampleDocument(key=key, group="g"))
    return repo


@pytest.mark.asyncio
async def test_get_all_with_max_zero_returns_everything(test_db):
    repo = await _three_documents(test_db)
    assert sorted(d.key for d in await repo.get_all_async(max=0)) == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_get_all_with_max_limits(test_db):
    repo = await _three_documents(test_db)
    assert len(await repo.get_all_async(max=2)) == 2


@pytest.mark.asyncio
async def test_get_list_with_max_zero_returns_every_match(test_db):
    repo = await _three_documents(test_db)
    assert len(await repo.get_list_async({"group": "g"}, max=0)) == 3


@pytest.mark.asyncio
async def test_paginated_list_with_limit_zero_returns_everything(test_db):
    repo = await _three_documents(test_db)
    rows = await repo.get_list_async_with_sort_and_paging({}, limit=0, page=1, sort=[("key", 1)])
    assert [d.key for d in rows] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_driver_refuses_to_list_zero(test_db):
    """Why the mapping matters: the driver itself no longer accepts 0."""
    await _three_documents(test_db)
    with pytest.raises(ValueError):
        await test_db["sample"].find({}).to_list(0)

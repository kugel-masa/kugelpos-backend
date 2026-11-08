# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""create_collection_async when another caller creates the same collection.

It checks list_collection_names and then calls create_collection, which checks
again on the client. Should another caller create the collection in between,
pymongo raises CollectionInvalid; it used to become a DatabaseException and fail
the whole tenant setup with a 500. Two tenants set up at once both create the
shared {prefix}_commons collections, so this is not hypothetical.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import CollectionInvalid, OperationFailure

from kugel_common.database.database import create_collection_async
from kugel_common.database.database_exceptions import DatabaseException


def _db(create_side_effect=None, existing=()):
    db = MagicMock()
    db.list_collection_names = AsyncMock(return_value=list(existing))
    db.create_collection = AsyncMock(side_effect=create_side_effect)
    return db


@pytest.mark.asyncio
async def test_a_collection_created_by_someone_else_in_between_is_not_an_error():
    db = _db(create_side_effect=CollectionInvalid("collection log_request already exists"))

    assert await create_collection_async("log_request", db) is False


@pytest.mark.asyncio
async def test_a_real_failure_still_raises():
    """Only CollectionInvalid means "it exists": a broader catch would read, say,
    missing privileges as a created collection and carry on."""
    db = _db(create_side_effect=OperationFailure("not authorized on db to execute command"))

    with pytest.raises(DatabaseException):
        await create_collection_async("log_request", db)


@pytest.mark.asyncio
async def test_the_usual_paths_are_unchanged():
    created = _db()
    assert await create_collection_async("log_request", created) is True
    created.create_collection.assert_awaited_once_with("log_request")

    existing = _db(existing=["log_request"])
    assert await create_collection_async("log_request", existing) is False
    existing.create_collection.assert_not_awaited()

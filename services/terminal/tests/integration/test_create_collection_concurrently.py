# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Creating one collection from several callers at once, against real MongoDB.

Callers check list_collection_names, then create_collection checks again on the
client. A gap between the two - another process, another replica, a slow event
loop - lets one caller create the collection after another has checked, and
pymongo then refuses the second create. The gap is made explicit here; without
it the callers' steps line up and the race does not show.
"""

import asyncio
import os
import random
import uuid

import pytest
import pytest_asyncio
from kugel_common.database.database import create_collection_async
from motor.motor_asyncio import AsyncIOMotorClient


class _GapAfterTheCheck:
    """The same database, with a scheduling gap after the existence check."""

    def __init__(self, db):
        self._db = db

    async def list_collection_names(self, *args, **kwargs):
        names = await self._db.list_collection_names(*args, **kwargs)
        await asyncio.sleep(random.uniform(0, 0.02))
        return names

    def __getattr__(self, name):
        return getattr(self._db, name)


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true"))
    database = client[f"test_create_collection_{uuid.uuid4().hex[:8]}"]
    yield database
    await client.drop_database(database.name)
    client.close()


@pytest.mark.asyncio
async def test_every_caller_succeeds_and_the_collection_exists(db):
    racing = _GapAfterTheCheck(db)
    for _ in range(30):
        name = f"c_{uuid.uuid4().hex[:8]}"

        results = await asyncio.gather(*[create_collection_async(name, racing) for _ in range(7)])

        assert results.count(True) >= 1
        assert name in await db.list_collection_names()

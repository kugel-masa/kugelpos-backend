# Copyright 2026 masa@kugel
"""The shared client lives and dies on the event loop that created it (#301, C-7, C-8).

A PyMongo async client is bound to its event loop, and `close()` must be awaited
on that loop: awaited from another one it raises. So the helpers remember which
loop made the client, close it there, and - when asked from another loop - drop
it with a warning rather than fail or pretend to have closed it.

"Another loop" is played by a second event loop driven from a worker thread.
"""
import asyncio
import logging

import pytest
from pymongo.errors import InvalidOperation


class OtherLoop:
    """A second event loop, run from a worker thread so the test's loop stays free."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()

    async def run(self, coro):
        return await asyncio.to_thread(self.loop.run_until_complete, coro)

    def close(self):
        self.loop.close()


@pytest.fixture
def other_loop():
    other = OtherLoop()
    yield other
    other.close()


async def _client_is_closed(client) -> bool:
    try:
        await client.server_info()
    except InvalidOperation:
        return True
    return False


@pytest.mark.asyncio
async def test_close_on_the_same_loop_closes_the_client(db_helper):
    client = await db_helper.get_client_async()
    await client.server_info()

    await db_helper.close_client_async()

    assert db_helper.client is None
    assert await _client_is_closed(client)


@pytest.mark.asyncio
async def test_closing_twice_is_harmless(db_helper):
    await db_helper.get_client_async()
    await db_helper.close_client_async()
    await db_helper.close_client_async()
    assert db_helper.client is None


@pytest.mark.asyncio
async def test_reset_on_the_same_loop_closes_and_a_new_client_follows(db_helper):
    first = await db_helper.get_client_async()
    await db_helper.reset_client_async()

    assert db_helper.client is None
    assert await _client_is_closed(first)

    second = await db_helper.get_client_async()
    assert second is not first
    await second.server_info()


@pytest.mark.asyncio
async def test_concurrent_get_client_creates_one_client(db_helper):
    clients = await asyncio.gather(*(db_helper.get_client_async() for _ in range(5)))
    assert all(c is clients[0] for c in clients)


@pytest.mark.asyncio
async def test_close_from_another_loop_drops_with_a_warning(db_helper, other_loop, caplog):
    foreign = await other_loop.run(db_helper.get_client_async())

    with caplog.at_level(logging.WARNING, logger=db_helper.__name__):
        await db_helper.close_client_async()

    assert db_helper.client is None
    assert any("another event loop" in r.getMessage() for r in caplog.records)
    # It was not closed from here - it is still usable on its own loop, and closed there.
    await other_loop.run(foreign.server_info())
    await other_loop.run(foreign.close())


@pytest.mark.asyncio
async def test_reset_from_another_loop_drops_with_a_warning(db_helper, other_loop, caplog):
    foreign = await other_loop.run(db_helper.get_client_async())

    with caplog.at_level(logging.WARNING, logger=db_helper.__name__):
        await db_helper.reset_client_async()

    assert db_helper.client is None
    assert any("another event loop" in r.getMessage() for r in caplog.records)
    await other_loop.run(foreign.close())


@pytest.mark.asyncio
async def test_get_client_from_another_loop_makes_a_new_client(db_helper, other_loop, caplog):
    foreign = await other_loop.run(db_helper.get_client_async())

    with caplog.at_level(logging.WARNING, logger=db_helper.__name__):
        mine = await db_helper.get_client_async()

    assert mine is not foreign
    assert db_helper.client is mine
    await mine.server_info()
    assert any("another event loop" in r.getMessage() for r in caplog.records)
    await other_loop.run(foreign.close())


@pytest.mark.asyncio
async def test_the_lock_works_on_each_loop(db_helper, other_loop):
    """A lock that one loop contended must not refuse the next loop.

    asyncio.Lock binds to the loop that first waits on it; a single module-level
    lock contended on one loop then raises on any other.
    """

    async def contend():
        clients = await asyncio.gather(*(db_helper.get_client_async() for _ in range(5)))
        return clients[0]

    foreign = await other_loop.run(contend())
    await other_loop.run(foreign.close())
    db_helper.client = None  # dropped on its own loop above; start this loop clean

    mine = await contend()
    await mine.server_info()

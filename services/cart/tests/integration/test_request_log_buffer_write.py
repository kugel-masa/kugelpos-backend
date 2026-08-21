# Copyright 2026 masa@kugel
"""The request-log buffer against a real MongoDB (issue #180).

Here rather than in `services/commons` because that package is unit-only by
design - its tests have no external dependencies - and the defect this covers is
precisely about the write reaching the database. The unit tier proves the buffer
hands the right documents to a mock; only a real backend proves the timer flush
completes against one.

The original symptom needed exactly this combination to appear: a single entry,
no size trigger, and a real write that suspends. With a mock that returns
without suspending the buffer looked fine.
"""

import asyncio
import os
import uuid

import pytest

from kugel_common.database import database as db_helper
from kugel_common.middleware.request_log_buffer import RequestLogBuffer
from kugel_common.models.documents.request_log_document import RequestLog

pytestmark = pytest.mark.asyncio


_accept_time_seq = 0


def _log(url, tenant_id):
    """A distinct accept_time per entry.

    Not cosmetic: the collection carries a unique index whose key columns
    `store_code` and `terminal_no` do not exist at the top level of a request log
    document, so it degenerates to (tenant_id, null, null, accept_time) and two
    entries sharing a timestamp collide (issue #182). Writing these tests is what
    demonstrated that on a live collection.
    """
    global _accept_time_seq
    _accept_time_seq += 1
    return RequestLog(
        tenant_id=tenant_id,
        client_info=RequestLog.ClientInfo(ip_address="127.0.0.1"),
        request_info=RequestLog.RequestInfo(
            method="POST",
            url=url,
            body=None,
            accept_time=f"2099-01-01T00:00:{_accept_time_seq:02d}.{uuid.uuid4().hex[:6]}",
        ),
        response_info=RequestLog.ResponseInfo(status_code=200, process_time_ms=1, body=None),
    )


async def _count(url):
    """Rows for this URL in the tenant database the buffer targets."""
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    return await db["log_request"].count_documents({"request_info.url": url})


async def test_the_idle_flush_writes_a_single_entry():
    """One entry, no size trigger, nothing but the timer to write it.

    This is the defect verbatim: the timer cancelled itself mid-flush and the
    entry vanished from the buffer without ever reaching MongoDB and without an
    error. It took 110 filler requests to make the log appear.
    """
    url = f"/integration/{uuid.uuid4().hex[:8]}"
    buffer = RequestLogBuffer(max_size=100, flush_interval=0.3)

    await buffer.add(_log(url, os.environ.get("TENANT_ID")))
    await asyncio.sleep(1.5)

    assert await _count(url) == 1, "the timer flush never reached MongoDB"


async def test_entries_added_during_a_write_are_flushed_too():
    """The buffer keeps working after a flush, without a size trigger."""
    first = f"/integration/{uuid.uuid4().hex[:8]}"
    second = f"/integration/{uuid.uuid4().hex[:8]}"
    buffer = RequestLogBuffer(max_size=100, flush_interval=0.3)

    await buffer.add(_log(first, os.environ.get("TENANT_ID")))
    await asyncio.sleep(0.5)
    await buffer.add(_log(second, os.environ.get("TENANT_ID")))
    await asyncio.sleep(1.5)

    assert await _count(first) == 1
    assert await _count(second) == 1, "the buffer stopped flushing after its first timer flush"


async def test_shutdown_writes_and_leaves_the_buffer_usable():
    """`shutdown` is how the suites force a flush, on a process-wide singleton."""
    before = f"/integration/{uuid.uuid4().hex[:8]}"
    after = f"/integration/{uuid.uuid4().hex[:8]}"
    buffer = RequestLogBuffer(max_size=100, flush_interval=0.3)

    await buffer.add(_log(before, os.environ.get("TENANT_ID")))
    await buffer.shutdown()
    assert await _count(before) == 1

    await buffer.add(_log(after, os.environ.get("TENANT_ID")))
    await asyncio.sleep(1.5)
    assert await _count(after) == 1, "the buffer was left closed by shutdown"


async def test_an_entry_is_written_once_not_twice():
    """The retry path stamps `_id` in place, so a repeat cannot double-count.

    Asserted against a real collection because that is where a duplicate would
    show up - a mock sink would happily collect the same document twice.
    """
    url = f"/integration/{uuid.uuid4().hex[:8]}"
    buffer = RequestLogBuffer(max_size=1, flush_interval=60.0)

    await buffer.add(_log(url, os.environ.get("TENANT_ID")))
    await buffer.shutdown()  # a second flush over the same entry, if any remained

    assert await _count(url) == 1

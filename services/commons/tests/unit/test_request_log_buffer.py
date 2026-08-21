# Copyright 2026 masa@kugel
"""Request-log buffer flush behaviour (issue #180).

The request log is an audit trail, so the property under test everywhere here is
the same one: an entry that entered the buffer either reaches the database or is
reported. Losing it quietly is the failure mode.

Every mocked write in this file yields (`await asyncio.sleep(0)` or more). That
is not decoration - a mock that returns without suspending never gives asyncio a
point at which to deliver a cancellation, so the original defect passes a test
written with one. Real I/O always suspends.
"""

import asyncio

import pytest

from kugel_common.middleware import request_log_buffer as buffer_module
from kugel_common.middleware.request_log_buffer import RequestLogBuffer
from kugel_common.models.documents.request_log_document import RequestLog

pytestmark = pytest.mark.asyncio


def _log(tenant_id="T0001", url="/api/v1/probe"):
    return RequestLog(
        tenant_id=tenant_id,
        client_info=RequestLog.ClientInfo(ip_address="127.0.0.1"),
        request_info=RequestLog.RequestInfo(method="POST", url=url, body=None, accept_time="2026-08-21T00:00:00"),
        response_info=RequestLog.ResponseInfo(status_code=200, process_time_ms=1, body=None),
    )


class _FakeCollection:
    def __init__(self, sink, fail_with=None):
        self._sink = sink
        self._fail_with = fail_with

    async def insert_many(self, docs, ordered=True):
        await asyncio.sleep(0.01)  # real I/O suspends; a mock that does not hides the defect
        if self._fail_with is not None:
            raise self._fail_with
        self._sink.extend(docs)


class _FakeDb:
    def __init__(self, sink, fail_with=None):
        self._sink = sink
        self._fail_with = fail_with

    def __getitem__(self, _name):
        return _FakeCollection(self._sink, self._fail_with)


class _Sink(list):
    """The documents written, plus a knob for arming a backend failure."""

    fail_with = None


@pytest.fixture
def written(monkeypatch):
    """Collect what the buffer writes; one sink across all target databases."""
    sink = _Sink()

    async def get_db_async(db_name):
        await asyncio.sleep(0)
        return _FakeDb(sink, sink.fail_with)

    monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
    return sink


class TestTheIdleFlush:
    """The trigger that lost the batch (issue #180)."""

    async def test_a_single_entry_reaches_the_database(self, written):
        # One request on a quiet service: too few to reach max_size, so the only
        # thing that can write it is the timer. Before the fix the timer
        # cancelled itself mid-flush and the entry vanished with no error.
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.2)

        await buffer.add(_log())
        await asyncio.sleep(0.8)

        assert len(written) > 0, "the timer flush lost the entry"
        assert buffer._buffer == []

    async def test_the_timer_survives_its_own_flush(self, written):
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.2)

        await buffer.add(_log(url="/first"))
        await asyncio.sleep(0.6)
        first = len(written)
        await buffer.add(_log(url="/second"))
        await asyncio.sleep(0.6)

        assert first > 0, "the first timer flush wrote nothing"
        assert len(written) > first, "the buffer stopped flushing after the first timer flush"


class TestTheSizeFlush:
    async def test_a_full_buffer_is_written(self, written):
        buffer = RequestLogBuffer(max_size=5, flush_interval=60.0)

        for _ in range(5):
            await buffer.add(_log())

        assert len(written) > 0
        assert buffer._buffer == []


class TestASteadyTrickle:
    """A rate below max_size must still reach the database."""

    async def test_entries_do_not_sit_forever_under_continuous_traffic(self, written):
        # Resetting the timer on every entry made this an *idle* timer: a stream
        # that never pauses for flush_interval and never reaches max_size kept
        # pushing the flush out, so entries could sit indefinitely.
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.3)

        for _ in range(12):
            await buffer.add(_log())
            await asyncio.sleep(0.1)  # steady, always shorter than flush_interval

        assert len(written) > 0, "a steady trickle never flushed"

    async def test_the_timer_is_not_rebuilt_for_every_entry(self, written):
        # The buffer exists to cut asyncio task churn (module docstring: ~200/sec
        # to ~2/sec). Re-arming per entry put that cost straight back.
        buffer = RequestLogBuffer(max_size=100, flush_interval=5.0)
        created = []
        real_create_task = asyncio.create_task

        def counting_create_task(coro, **kwargs):
            task = real_create_task(coro, **kwargs)
            created.append(task)
            return task

        buffer_module.asyncio.create_task = counting_create_task
        try:
            for _ in range(20):
                await buffer.add(_log())
        finally:
            buffer_module.asyncio.create_task = real_create_task
            await buffer.shutdown()

        assert len(created) == 1, f"{len(created)} timer tasks for 20 entries"


class TestShutdown:
    async def test_shutdown_writes_what_is_left(self, written):
        buffer = RequestLogBuffer(max_size=100, flush_interval=60.0)

        await buffer.add(_log())
        await buffer.shutdown()

        assert len(written) > 0


class TestAFailedWrite:
    """A write that fails must not silently take the entries with it."""

    async def test_an_unreachable_backend_keeps_the_entries_for_a_retry(self, written, monkeypatch):
        from pymongo.errors import ServerSelectionTimeoutError

        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        await buffer.add(_log(url="/during-outage-1"))
        await buffer.add(_log(url="/during-outage-2"))
        assert written == [], "precondition: the write was supposed to fail"

        # Backend comes back; the next flush must carry the earlier entries too.
        written.fail_with = None
        await buffer.add(_log(url="/after-1"))
        await buffer.add(_log(url="/after-2"))

        # Assert on the entries, not the document count: each entry is written to
        # both the commons and the tenant database, so counting documents would
        # pass on the two later entries alone.
        urls = {d["request_info"]["url"] for d in written}
        assert urls == {"/during-outage-1", "/during-outage-2", "/after-1", "/after-2"}, (
            f"entries lost across the outage: {sorted(urls)}"
        )

    async def test_a_refusal_by_the_server_is_reported_and_not_retried_forever(self, written, caplog):
        from pymongo.errors import BulkWriteError

        written.fail_with = BulkWriteError({"writeErrors": [{"code": 11000}], "nInserted": 1})
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        with caplog.at_level("ERROR"):
            await buffer.add(_log())
            await buffer.add(_log())

        # The server answered and refused specific documents; repeating the batch
        # repeats the refusal, so it is dropped - but it must be said out loud.
        assert any("request log" in r.message.lower() for r in caplog.records)
        assert buffer._pending_total() == 0

    async def test_the_retry_backlog_is_bounded(self, written):
        from pymongo.errors import ServerSelectionTimeoutError

        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=100, flush_interval=60.0)

        entries = 1200
        for _ in range(entries):
            await buffer.add(_log())

        # Each entry is written to two databases, so an unbounded backlog would
        # hold 2400 documents. Asserting against the offered volume rather than
        # against MAX_PENDING_DOCS alone: the latter passes whatever the constant
        # is set to, including no bound at all.
        offered = entries * 2
        assert buffer._pending_total() < offered, "the backlog kept everything; nothing was dropped"
        assert buffer._pending_total() <= buffer_module.MAX_PENDING_DOCS

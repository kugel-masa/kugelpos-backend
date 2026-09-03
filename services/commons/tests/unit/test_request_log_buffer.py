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

    async def insert_one(self, doc):
        # The per-document rewrite a batch-level refusal falls back to (#210).
        # It fails the same way insert_many does, because the arming knob is
        # about the backend rather than about one document.
        await asyncio.sleep(0.01)
        if self._fail_with is not None:
            raise self._fail_with
        self._sink.append(doc)


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


class TestOneTargetDoesNotStarveAnother:
    """Every entry is written to the commons AND the tenant database."""

    async def test_the_retry_budget_is_shared_between_databases(self, written):
        from pymongo.errors import ServerSelectionTimeoutError

        # An outage fails both targets at once. A first-come budget let commons
        # take the whole allowance and dropped 100% of the per-tenant trail -
        # which is the copy an auditor reads.
        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=100, flush_interval=60.0)

        for _ in range(1200):
            await buffer.add(_log(tenant_id="T0001"))

        per_db = {name: len(docs) for name, docs in buffer._pending.items()}
        assert len(per_db) == 2, f"expected both targets to be held back: {per_db}"
        assert all(n > 0 for n in per_db.values()), f"one target was starved: {per_db}"


class TestCancellationMidWrite:
    """A size-triggered flush runs on the request task that filled the buffer."""

    async def test_a_cancelled_flush_keeps_the_batch(self, written, monkeypatch):
        # The batch belongs to every request in the window, not to the client
        # whose connection dropped.
        buffer = RequestLogBuffer(max_size=3, flush_interval=60.0)

        async def add_until_flush():
            for _ in range(3):
                await buffer.add(_log())

        task = asyncio.create_task(add_until_flush())
        await asyncio.sleep(0.005)  # inside the write, which sleeps 0.01
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert written == [], "precondition: the write should not have completed"
        assert buffer._pending_total() > 0, "the cancelled flush dropped the batch"

    async def test_the_kept_batch_is_written_by_the_next_flush(self, written):
        buffer = RequestLogBuffer(max_size=3, flush_interval=60.0)

        async def add_until_flush():
            for _ in range(3):
                await buffer.add(_log(url="/cancelled"))

        task = asyncio.create_task(add_until_flush())
        await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        for _ in range(3):
            await buffer.add(_log(url="/later"))

        urls = {d["request_info"]["url"] for d in written}
        assert "/cancelled" in urls, f"the cancelled batch never reached the database: {sorted(urls)}"


class TestTheFlushDoesNotHoldUpRequests:
    async def test_the_lock_is_free_while_the_write_is_in_flight(self, written, monkeypatch):
        """Holding the lock across the write would make the audit log stall the
        requests it audits: an unreachable backend costs a server-selection
        timeout per flush, and every concurrent `add` would wait behind it."""
        started = asyncio.Event()
        release = asyncio.Event()

        class _SlowCollection:
            async def insert_many(self, docs, ordered=True):
                started.set()
                await release.wait()
                written.extend(docs)

        class _SlowDb:
            def __getitem__(self, _name):
                return _SlowCollection()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _SlowDb()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        flusher = asyncio.create_task(_fill(buffer, 2))
        await asyncio.wait_for(started.wait(), timeout=1.0)

        # The write is in flight; another request must not be blocked by it.
        await asyncio.wait_for(buffer.add(_log(url="/concurrent")), timeout=0.5)

        release.set()
        await flusher
        assert buffer._buffer, "the concurrent entry never made it into the buffer"


async def _fill(buffer, n):
    for _ in range(n):
        await buffer.add(_log())


class TestTheBacklogUnderAProlongedOutage:
    async def test_the_bound_holds_across_repeated_failures(self, written):
        from pymongo.errors import ServerSelectionTimeoutError

        # `max(1, ...)` as a share floor looks harmless and leaks a document per
        # database per flush for as long as the backend stays down.
        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=10, flush_interval=60.0)

        for _ in range(1500):  # the bound is reached after ~100 flushes
            await buffer.add(_log())

        assert buffer._pending_total() <= buffer_module.MAX_PENDING_DOCS, (
            f"the backlog grew past its bound: {buffer._pending_total()}"
        )

    async def test_a_full_backlog_keeps_nothing_rather_than_everything(self, written):
        from pymongo.errors import ServerSelectionTimeoutError

        # docs[-0:] is the whole list; a share of zero has to mean zero.
        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=10, flush_interval=60.0)

        for _ in range(1500):
            await buffer.add(_log())
        before = buffer._pending_total()
        for _ in range(100):
            await buffer.add(_log())

        assert buffer._pending_total() <= max(before, buffer_module.MAX_PENDING_DOCS)


class TestATimerIsAlwaysArmedForWaitingEntries:
    async def test_an_entry_added_during_a_write_still_gets_flushed(self, written, monkeypatch):
        """Leaving the timer reference set across the write is how a buffer ends
        up holding entries with nothing scheduled to flush them: the concurrent
        `add` sees a task that is not done and skips arming, and the timer that
        is already on its way out then clears the reference."""
        started = asyncio.Event()
        release = asyncio.Event()

        class _SlowCollection:
            async def insert_many(self, docs, ordered=True):
                started.set()
                await release.wait()
                written.extend(docs)

        class _SlowDb:
            def __getitem__(self, _name):
                return _SlowCollection()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _SlowDb()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.2)

        await buffer.add(_log(url="/first"))
        await asyncio.wait_for(started.wait(), timeout=1.0)  # the timer flush is in flight
        await buffer.add(_log(url="/second"))  # arrives while the write is in flight
        release.set()

        await asyncio.sleep(1.0)  # room for another whole timer cycle

        urls = {d["request_info"]["url"] for d in written}
        assert "/second" in urls, f"the entry added during the write was never flushed: {sorted(urls)}"


class TestTheBudgetUnderConcurrentFlushes:
    """Writes run outside the lock, so two flushes can be in flight at once.

    In the ordinary path the backlog is drained into the batch before the write,
    so `_pending` is empty when the retry decision is made and the budget is the
    whole allowance. Two overlapping flushes are the case where it is not - and
    where `docs[-share:]` with a share of zero would keep the entire batch
    instead of nothing, turning a full backlog into an unbounded one.
    """

    async def test_a_second_flush_cannot_push_the_backlog_past_the_bound(self, written):
        buffer = RequestLogBuffer(max_size=10, flush_interval=60.0)
        batch = [{"n": i} for i in range(800)]

        buffer._keep_for_retry([("db_a", list(batch)), ("db_b", list(batch))])
        first = buffer._pending_total()
        # A flush that overlapped the first one now reports its own failure while
        # the backlog is already populated.
        buffer._keep_for_retry([("db_a", list(batch)), ("db_b", list(batch))])

        assert first <= buffer_module.MAX_PENDING_DOCS
        assert buffer._pending_total() <= buffer_module.MAX_PENDING_DOCS, (
            f"a concurrent flush pushed the backlog to {buffer._pending_total()}"
        )


class TestShutdownRacingAFlush:
    """Cancelling a task does not stop it where the cancel is called."""

    @staticmethod
    def _slow_backend(monkeypatch, written, started, release):
        class _SlowCollection:
            async def insert_many(self, docs, ordered=True):
                started.set()
                await release.wait()
                written.extend(docs)

        class _SlowDb:
            def __getitem__(self, _name):
                return _SlowCollection()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _SlowDb()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)

    async def test_a_timer_flush_in_flight_is_not_abandoned(self, written, monkeypatch):
        # A timer that got as far as writing has already had its reference
        # cleared by _take_batch, so `_cancel_timer` cannot reach it and
        # shutdown cannot see it. Returning anyway leaves that batch to die with
        # the event loop - the same silent loss as #180, relocated to shutdown.
        started, release = asyncio.Event(), asyncio.Event()
        self._slow_backend(monkeypatch, written, started, release)
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.1)

        await buffer.add(_log(url="/in-flight"))
        await asyncio.wait_for(started.wait(), timeout=1.0)  # the timer is inside the write

        shutdown = asyncio.create_task(buffer.shutdown())
        await asyncio.sleep(0.05)
        assert not shutdown.done(), "shutdown returned while a write was still in flight"

        release.set()
        await asyncio.wait_for(shutdown, timeout=2.0)

        urls = {d["request_info"]["url"] for d in written}
        assert "/in-flight" in urls, f"the in-flight batch was abandoned: written={sorted(urls)}"
        assert buffer._buffer == []
        assert buffer._pending_total() == 0

    async def test_the_final_write_arms_no_timer(self, written):
        # A failed write asks for a retry by arming a timer. During shutdown that
        # is a task on a loop about to close: it never runs, and asyncio reports
        # it as destroyed-while-pending.
        from pymongo.errors import ServerSelectionTimeoutError

        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.1)

        await buffer.add(_log())
        await buffer.shutdown()

        assert buffer._timer_task is None, "shutdown scheduled a timer on a closing loop"

    async def test_the_buffer_still_works_after_a_shutdown(self, written):
        # shutdown means "flush everything now", and the suites use it that way -
        # on a process-wide singleton. Holding the closing flag past the call
        # would make the first shutdown the last flush the process performs, and
        # every entry accepted afterwards would sit with no timer to write it.
        buffer = RequestLogBuffer(max_size=100, flush_interval=0.2)

        await buffer.add(_log(url="/before"))
        await buffer.shutdown()
        await buffer.add(_log(url="/after"))
        await asyncio.sleep(0.8)

        urls = {d["request_info"]["url"] for d in written}
        assert "/after" in urls, f"the buffer stopped flushing after a shutdown: {sorted(urls)}"


class TestAnEmptyBatchIsNeverOffered:
    async def test_a_full_backlog_leaves_no_empty_list_behind(self, written):
        # insert_many([]) raises TypeError("documents must be a non-empty list"),
        # which would fail the whole target for that flush.
        buffer = RequestLogBuffer(max_size=10, flush_interval=60.0)
        buffer._pending = {"db_a": [{"n": i} for i in range(buffer_module.MAX_PENDING_DOCS)]}

        buffer._keep_for_retry([("db_b", [{"n": 1}])])

        assert buffer._pending.get("db_b") is None, "an empty batch was left in the backlog"

    async def test_an_empty_batch_is_skipped_rather_than_written(self, written, monkeypatch):
        calls = []

        class _Collection:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0)
                calls.append(len(docs))
                if not docs:
                    raise TypeError("documents must be a non-empty list")
                written.extend(docs)

        class _Db:
            def __getitem__(self, _name):
                return _Collection()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=100, flush_interval=60.0)

        await buffer._write({"db_a": [], "db_b": [{"n": 1}]})

        assert calls == [1], f"an empty batch reached insert_many: {calls}"


class TestWhichFailuresAreWorthRepeating:
    async def test_a_connection_failure_wrapped_by_the_db_helper_is_still_retried(self, written):
        # get_db_async wraps everything it catches in a DatabaseException, so an
        # unreachable backend can arrive with the ConnectionFailure only in
        # __cause__. A classification that tested the exception in hand would
        # turn every outage into permanent loss.
        from pymongo.errors import ServerSelectionTimeoutError

        wrapped = RuntimeError("Failed to get database")
        wrapped.__cause__ = ServerSelectionTimeoutError("backend down")
        written.fail_with = wrapped
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        await buffer.add(_log())
        await buffer.add(_log())

        assert buffer._pending_total() > 0, "a wrapped outage was treated as permanent"

    async def test_a_failure_a_repeat_cannot_help_is_not_retried(self, written, caplog):
        # A document the driver refuses to encode fails the same way every time.
        # Holding it would keep the backlog against entries that could be written.
        from bson.errors import InvalidDocument

        written.fail_with = InvalidDocument("cannot encode object")
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        with caplog.at_level("ERROR"):
            await buffer.add(_log())
            await buffer.add(_log())

        assert buffer._pending_total() == 0
        assert any("lost" in r.message.lower() for r in caplog.records), (
            "a permanent failure dropped the entries without saying so"
        )


class TestNothingAccumulates:
    async def test_inflight_is_emptied_after_a_failed_write(self, written):
        # _inflight is what shutdown waits on. A task left in it would be waited
        # for forever on the next shutdown, and the set would grow with every
        # failure.
        from pymongo.errors import ServerSelectionTimeoutError

        written.fail_with = ServerSelectionTimeoutError("backend down")
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        for _ in range(6):
            await buffer.add(_log())

        assert buffer._inflight == set()

    async def test_inflight_is_emptied_after_a_cancelled_write(self, written):
        buffer = RequestLogBuffer(max_size=3, flush_interval=60.0)

        async def add_until_flush():
            for _ in range(3):
                await buffer.add(_log())

        task = asyncio.create_task(add_until_flush())
        await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buffer._inflight == set()

    async def test_the_buffer_does_not_grow_while_writes_succeed(self, written):
        buffer = RequestLogBuffer(max_size=5, flush_interval=60.0)

        for _ in range(50):
            await buffer.add(_log())

        assert buffer._buffer == []
        assert buffer._pending_total() == 0
        assert buffer._inflight == set()


class TestOverlappingFlushes:
    async def test_two_flushes_in_flight_lose_nothing(self, written, monkeypatch):
        """Writes run outside the lock, so a second flush can start while the
        first is still writing. Every entry must still land exactly once."""
        gate = asyncio.Event()

        class _GatedCollection:
            async def insert_many(self, docs, ordered=True):
                await gate.wait()
                await asyncio.sleep(0)
                written.extend(docs)

        class _GatedDb:
            def __getitem__(self, _name):
                return _GatedCollection()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _GatedDb()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        # Two independent tasks, each filling the buffer to its size trigger, so
        # both are inside a write at the same time.
        async def fill(tag):
            for i in range(2):
                await buffer.add(_log(url=f"/{tag}-{i}"))

        tasks = [asyncio.create_task(fill("a")), asyncio.create_task(fill("b"))]
        await asyncio.sleep(0.02)
        gate.set()
        await asyncio.gather(*tasks)
        await buffer.shutdown()

        urls = [d["request_info"]["url"] for d in written]
        expected = {"/a-0", "/a-1", "/b-0", "/b-1"}
        assert set(urls) >= expected, f"entries lost across overlapping flushes: {sorted(set(urls))}"
        # Each entry goes to the commons and the tenant database, and no more.
        for url in expected:
            assert urls.count(url) == 2, f"{url} written {urls.count(url)} times, expected 2"


class TestOneDocumentDoesNotTakeTheBatch:
    """Issue #210.

    BSON stores an integer in eight bytes and a Python int has no width, so a
    26-digit barcode in a request body parses fine and then refuses to encode.
    That happens client-side, ahead of the wire, so `ordered=False` has nothing
    to order: without a fix, one request discards every other audit record in
    the batch, and the only trace is an ERROR line naming a count.
    """

    async def test_a_number_too_wide_for_bson_is_written_as_text(self, written):
        # The value known to cause it, made encodable on the way in. A request
        # log is an audit record - nothing does arithmetic on it - so the
        # barcode survives as its own digits, just typed as a string.
        barcode = 12345678901234567890123456
        buffer = RequestLogBuffer(max_size=1, flush_interval=60.0)

        log = _log()
        log.request_info.body = {"barcode": barcode, "lines": [{"itemCode": barcode}]}
        await buffer.add(log)

        stored = written[0]["request_info"]["body"]
        assert stored["barcode"] == str(barcode), f"a wide int reached the driver: {stored['barcode']!r}"
        assert stored["lines"][0]["itemCode"] == str(barcode), "nested values were not coerced"

    async def test_ordinary_values_are_left_alone(self, written):
        # The coercion must not rewrite the log it is protecting. In particular
        # bool is a subclass of int, so a True measured as 1 would come back as
        # the string "True" and change what the audit trail says.
        buffer = RequestLogBuffer(max_size=1, flush_interval=60.0)

        log = _log()
        log.request_info.body = {"qty": 3, "unitPrice": 1.5, "isVoid": True, "code": "0001", "note": None}
        await buffer.add(log)

        assert written[0]["request_info"]["body"] == {
            "qty": 3,
            "unitPrice": 1.5,
            "isVoid": True,
            "code": "0001",
            "note": None,
        }

    async def test_a_batch_refused_as_a_batch_loses_only_the_bad_document(self, monkeypatch, caplog):
        # The class of the problem rather than the case: whatever makes one
        # document unencodable, the other 99 were fine and must still be written.
        sink = []

        class _RefusesTheBatch:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                raise OverflowError("MongoDB can only handle up to 8-byte ints")

            async def insert_one(self, doc):
                await asyncio.sleep(0.01)
                if doc["request_info"]["url"] == "/bad":
                    raise OverflowError("MongoDB can only handle up to 8-byte ints")
                sink.append(doc)

        class _Db:
            def __getitem__(self, _name):
                return _RefusesTheBatch()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=4, flush_interval=60.0)

        with caplog.at_level("INFO"):
            for url in ("/a", "/bad", "/b", "/c"):
                await buffer.add(_log(url=url))

        urls = sorted({d["request_info"]["url"] for d in sink})
        assert urls == ["/a", "/b", "/c"], f"unrelated entries were discarded with the bad one: {urls}"
        assert buffer._pending_total() == 0, "an unencodable document was held for a retry it cannot survive"
        # A count is not enough to chase: the entry that was actually lost is named.
        assert any("/bad" in r.message for r in caplog.records if r.levelname == "ERROR"), (
            "the lost entry was not named"
        )

    async def test_a_document_already_written_is_not_counted_as_lost(self, monkeypatch, caplog):
        # insert_many stamps _id in place, so a document the server took before
        # the batch failed comes back from the rewrite as a duplicate. It is in
        # the database - reporting it as lost would send an operator hunting for
        # an entry that is right there.
        from pymongo.errors import DuplicateKeyError

        class _AlreadyHasThem:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                raise OverflowError("MongoDB can only handle up to 8-byte ints")

            async def insert_one(self, doc):
                await asyncio.sleep(0.01)
                raise DuplicateKeyError("E11000 duplicate key error")

        class _Db:
            def __getitem__(self, _name):
                return _AlreadyHasThem()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        with caplog.at_level("INFO"):
            await buffer.add(_log(url="/a"))
            await buffer.add(_log(url="/b"))

        assert not [r for r in caplog.records if r.levelname == "ERROR"], (
            "a document already in the database was reported lost"
        )

    async def test_an_outage_during_the_rewrite_keeps_the_entries(self, monkeypatch):
        # The rewrite is not a licence to drop: a document that failed for a
        # reason a retry can fix is still owed the next flush.
        from pymongo.errors import ConnectionFailure

        attempts = []

        class _DiesMidway:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                raise OverflowError("MongoDB can only handle up to 8-byte ints")

            async def insert_one(self, doc):
                await asyncio.sleep(0.01)
                attempts.append(doc["request_info"]["url"])
                raise ConnectionFailure("backend went away")

        class _Db:
            def __getitem__(self, _name):
                return _DiesMidway()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=4, flush_interval=60.0)

        for url in ("/a", "/b", "/c", "/d"):
            await buffer.add(_log(url=url))

        # Every entry is kept, including the one whose own write failed: it was
        # the backend that went away, not the document.
        assert buffer._pending_total() == 8, (  # 4 entries x 2 target databases
            f"an outage during the rewrite lost entries: {buffer._pending_total()} of 8 kept"
        )
        # And the outage was believed the first time. Each further attempt would
        # spend a server-selection timeout (5 s configured) discovering the same
        # thing, on the request task that filled the buffer.
        assert len(attempts) == 2, (  # one per target database
            f"the rewrite kept trying an unreachable backend: {len(attempts)} attempts"
        )

    async def test_a_refusal_of_the_command_is_not_repeated_per_document(self, monkeypatch, caplog):
        # An authorization failure is not about any one document - the server
        # will refuse each of them identically. Expanding it into one write per
        # entry buys nothing and costs a round trip and an ERROR line each.
        from pymongo.errors import OperationFailure

        attempts = []

        class _RefusesTheCommand:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                raise OperationFailure("not authorized on db to execute command insert")

            async def insert_one(self, doc):  # pragma: no cover - must not be reached
                await asyncio.sleep(0.01)
                attempts.append(doc)

        class _Db:
            def __getitem__(self, _name):
                return _RefusesTheCommand()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=50, flush_interval=60.0)

        with caplog.at_level("ERROR"):
            for i in range(50):
                await buffer.add(_log(url=f"/{i}"))

        assert attempts == [], f"a command-level refusal was retried per document: {len(attempts)} times"
        assert len(caplog.records) == 2, (  # one per target database
            f"a command-level refusal produced {len(caplog.records)} error lines, expected one per database"
        )

    async def test_a_refusal_of_one_document_by_the_server_is_still_rewritten(self, monkeypatch):
        # The counterpart: a WriteError IS about the document it names, so the
        # rewrite still applies. Issue #210 asks for the loss to be bounded to
        # the offending entry "whatever the cause", not only for the encoding
        # failure that found it.
        from pymongo.errors import WriteError

        sink = []

        class _RefusesOneDocument:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                raise WriteError("document failed validation")

            async def insert_one(self, doc):
                await asyncio.sleep(0.01)
                if doc["request_info"]["url"] == "/bad":
                    raise WriteError("document failed validation")
                sink.append(doc)

        class _Db:
            def __getitem__(self, _name):
                return _RefusesOneDocument()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=3, flush_interval=60.0)

        for url in ("/a", "/bad", "/b"):
            await buffer.add(_log(url=url))

        assert sorted({d["request_info"]["url"] for d in sink}) == ["/a", "/b"]

    async def test_an_unreachable_database_is_not_rewritten_document_by_document(self, monkeypatch):
        # The rewrite exists for a batch the driver refused; when there was no
        # collection to write to at all, repeating it per document would only
        # repeat the same failure once per entry.
        from bson.errors import InvalidDocument

        calls = []

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            calls.append(db_name)
            raise InvalidDocument("no database for you")

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=50, flush_interval=60.0)

        for i in range(50):
            await buffer.add(_log(url=f"/{i}"))

        # Two target databases, one attempt each - not one attempt per document.
        assert len(calls) == 2, f"a failure to reach the database was retried per document: {len(calls)} attempts"


class TestTheLimitsOfTheCoercion:
    """`_bson_safe` stops descending at a depth, and says so. Test what that means."""

    @staticmethod
    def _nest(depth, leaf):
        top = current = {}
        for _ in range(depth):
            current["a"] = {}
            current = current["a"]
        current.update(leaf)
        return top

    def test_a_hostile_depth_does_not_exhaust_the_stack(self):
        # The cap is there so that a body nested deeper than the interpreter
        # can recurse does not turn a flush into a RecursionError. `json.loads`
        # accepts bodies far deeper than this.
        assert buffer_module._bson_safe(self._nest(3000, {"quantity": 1})) is not None

    def test_a_wide_int_within_the_cap_is_coerced(self):
        barcode = 12345678901234567890123456
        safe = buffer_module._bson_safe(self._nest(30, {"barcode": barcode}))

        current = safe
        for _ in range(30):
            current = current["a"]
        assert current["barcode"] == str(barcode)

    def test_a_wide_int_past_the_cap_is_left_for_the_rewrite(self):
        # The honest limit: past the cap the value is returned as it is, so it
        # is still unencodable. That is not an oversight - it is why
        # `_rewrite_individually` exists, and why the cap's comment names it as
        # the backstop. This pins the boundary so a future change to either
        # side has to face the other.
        barcode = 12345678901234567890123456
        safe = buffer_module._bson_safe(self._nest(40, {"barcode": barcode}))

        current = safe
        for _ in range(40):
            current = current["a"]
        assert current["barcode"] == barcode, "past the cap the value is untouched, by design"

    def test_the_boundary_is_where_it_says_it_is(self):
        barcode = 2**64
        deep_enough = buffer_module._bson_safe(self._nest(31, {"n": barcode}))
        too_deep = buffer_module._bson_safe(self._nest(32, {"n": barcode}))

        current = deep_enough
        for _ in range(31):
            current = current["a"]
        assert current["n"] == str(barcode), "the last level inside the cap is still coerced"

        current = too_deep
        for _ in range(32):
            current = current["a"]
        assert current["n"] == barcode, "the first level past the cap is not"


class TestCancellationDuringTheRewrite:
    """The rewrite runs one write at a time, so there is more of it to cancel."""

    async def test_a_cancelled_rewrite_keeps_every_entry(self, monkeypatch):
        # A size-triggered flush runs on the request task, so a client
        # disconnect cancels it - and the rewrite is the slowest part of that
        # path, which makes it the likeliest place to be cancelled. The batch
        # belongs to every request in the window, not to the one that left.
        written = []

        class _CancelledMidway:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                raise OverflowError("MongoDB can only handle up to 8-byte ints")

            async def insert_one(self, doc):
                await asyncio.sleep(0.01)
                if len(written) >= 2:
                    raise asyncio.CancelledError()
                written.append(doc["request_info"]["url"])

        class _Db:
            def __getitem__(self, _name):
                return _CancelledMidway()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=5, flush_interval=60.0)

        async def fill():
            for i in range(5):
                await buffer.add(_log(url=f"/{i}"))

        task = asyncio.create_task(fill())
        with pytest.raises(asyncio.CancelledError):
            await task

        # The rewrite really was under way when the cancellation landed - two
        # documents had already been written one at a time. Without this the
        # test would still pass if the cancellation arrived before the rewrite
        # started, which is a different path and one already covered.
        assert len(written) == 2, f"the rewrite was not reached: wrote {written}"

        # CancelledError is a BaseException, so it passes through the
        # per-document `except Exception` untouched and reaches the handler in
        # _write_batches, which keeps what was in flight.
        assert buffer._pending_total() > 0, "a cancelled rewrite dropped the batch"

    async def test_what_the_cancelled_rewrite_kept_is_written_next_time(self, monkeypatch):
        state = {"cancel": True, "written": []}

        class _CancelsOnce:
            async def insert_many(self, docs, ordered=True):
                await asyncio.sleep(0.01)
                if state["cancel"]:
                    raise OverflowError("MongoDB can only handle up to 8-byte ints")
                state["written"].extend(d["request_info"]["url"] for d in docs)

            async def insert_one(self, doc):
                await asyncio.sleep(0.01)
                raise asyncio.CancelledError()

        class _Db:
            def __getitem__(self, _name):
                return _CancelsOnce()

        async def get_db_async(db_name):
            await asyncio.sleep(0)
            return _Db()

        monkeypatch.setattr(buffer_module.db_helper, "get_db_async", get_db_async)
        buffer = RequestLogBuffer(max_size=2, flush_interval=60.0)

        async def fill():
            await buffer.add(_log(url="/cancelled-1"))
            await buffer.add(_log(url="/cancelled-2"))

        task = asyncio.create_task(fill())
        with pytest.raises(asyncio.CancelledError):
            await task

        # The backend recovers; the next flush must carry the earlier entries.
        state["cancel"] = False
        await buffer.add(_log(url="/later-1"))
        await buffer.add(_log(url="/later-2"))

        assert "/cancelled-1" in state["written"], (
            f"the cancelled rewrite lost its entries: {sorted(set(state['written']))}"
        )

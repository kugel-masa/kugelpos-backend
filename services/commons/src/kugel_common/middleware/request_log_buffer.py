# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Buffered request log writer for MongoDB

Batches request log documents and writes them to MongoDB using insert_many,
reducing the number of create_task calls on the event loop from ~200/sec to ~2/sec.

Flush triggers:
- Buffer reaches max_size (default: 100)
- The oldest buffered entry reaches flush_interval seconds (default: 5.0)
- Service shutdown (via shutdown() method)

The request log is an audit trail, so the invariant this module owes its callers
is that an entry it accepted either reaches the database or is reported. Issue
#180 was a violation of it in silence, and the two rules that keep it are worth
stating because neither is obvious from the code alone:

- **Never cancel the task that is doing the flushing.** The timer calls the
  flush, and the flush cancels the timer; when those are the same task the
  cancellation lands on the next ``await`` - inside the write - and ``_timer``
  swallows it. The entries were already out of the buffer, so they disappeared
  with no error at all.
- **Only retry what a retry can fix.** An unreachable backend is transient and
  the batch is kept; documents the server actively refused are not, and
  repeating them just repeats the refusal.
- **One document must not take the batch with it.** Issue #210: a number too
  wide for BSON fails to encode client-side, ahead of the wire, so
  ``ordered=False`` spares nothing and a single request discards up to
  ``max_size`` unrelated audit records. Two things keep that bounded - the
  values known to cause it are made encodable on the way in (``_bson_safe``),
  and a batch refused as a batch is offered again one document at a time
  (``_rewrite_individually``), which loses only what is genuinely unwritable
  and names it.
"""

import asyncio
from logging import getLogger
from typing import Any, List

from pymongo.errors import BulkWriteError, ConnectionFailure, DuplicateKeyError

from kugel_common.database import database as db_helper
from kugel_common.models.documents.request_log_document import RequestLog
from kugel_common.config.settings import settings

logger = getLogger(__name__)

# Ceiling on documents held back for a retry. A backend that stays unreachable
# must not turn the audit buffer into a memory leak, so the backlog is a sliding
# window of the most recent documents: during an ongoing outage those are the
# ones an operator is looking for, and no bound can keep the trail complete.
MAX_PENDING_DOCS = 1000

# BSON stores an integer in eight bytes; a Python int has no width at all. So a
# request body carrying a 26-digit number - a barcode, in the case that found
# this - parses into a perfectly ordinary `int` and then cannot be encoded
# (issue #210). The encoding happens client-side, ahead of the wire, which is
# what makes it a batch-level failure: `ordered=False` has nothing to order
# because no document reached the server at all.
_BSON_INT_MIN = -(2**63)
_BSON_INT_MAX = 2**63 - 1

# Nesting depth past which coercion stops descending, on the same reasoning as
# the logging middleware's own cap: a body deeper than this is not something the
# audit path needs to walk, and the cap keeps a hostile payload from turning the
# flush into a RecursionError. What the cap leaves unencodable is not lost -
# `_rewrite_individually` is the backstop for it, and for every other reason a
# document may refuse to encode.
_MAX_COERCE_DEPTH = 32


def _bson_safe(value: Any, depth: int = 0) -> Any:
    """Return `value` with every integer BSON cannot encode replaced by its text.

    A request log is an audit record - nothing does arithmetic on it - so a
    26-digit barcode is just as readable as the string "12345678901234567890123456",
    and keeping it that way is what lets the other 99 documents in the batch be
    written (issue #210).

    Args:
        value: A document, or any value within one
        depth: Current nesting depth

    Returns:
        A copy with out-of-range integers rendered as decimal strings
    """
    # bool is a subclass of int and always encodable, so it has to be answered
    # before the range test - otherwise True would be measured as 1.
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if _BSON_INT_MIN <= value <= _BSON_INT_MAX else str(value)
    if depth >= _MAX_COERCE_DEPTH:
        return value
    if isinstance(value, dict):
        return {key: _bson_safe(member, depth + 1) for key, member in value.items()}
    if isinstance(value, list):
        return [_bson_safe(member, depth + 1) for member in value]
    return value


def _describe(doc: dict) -> str:
    """Name one document well enough for an operator to find what was lost."""
    request = doc.get("request_info") or {}
    return (
        f"{request.get('method', '?')} {request.get('url', '?')} "
        f"at {request.get('accept_time', '?')} (tenant={doc.get('tenant_id')})"
    )


def _is_transient(error: BaseException) -> bool:
    """Whether a failed write is worth repeating.

    Walks the cause chain rather than testing the exception in hand:
    ``get_db_async`` wraps everything it catches in a DatabaseException, so a
    backend that is simply unreachable can arrive here with the ConnectionFailure
    only in ``__cause__`` - and a classification that missed it would quietly
    turn every outage into permanent loss.

    Everything else is treated as permanent on purpose. The failures that are
    not connection failures are the ones a repeat cannot help: a document the
    driver refuses to encode, one over the BSON size limit, a duplicate key.
    Retrying those forever would hold the backlog against the entries that could
    still be written.
    """
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, ConnectionFailure):
            return True
        seen.add(id(error))
        error = error.__cause__
    return False


class RequestLogBuffer:
    """Batches RequestLog documents and flushes them to MongoDB via insert_many."""

    def __init__(self, max_size: int = 100, flush_interval: float = 5.0):
        self._buffer: List[RequestLog] = []
        self._max_size = max_size
        self._flush_interval = flush_interval
        self._timer_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        # Documents whose write failed for a reason a retry could fix, per target
        # database, carried into the next flush. Bounded by MAX_PENDING_DOCS.
        #
        # Mutated without the lock from _write, which runs outside it. That is
        # safe because every mutation here is a plain dict/list operation with no
        # await inside it, so it cannot interleave with another one; only the
        # relative order of two concurrent flushes is unspecified, and these are
        # timestamped audit records rather than a sequence.
        self._pending: dict[str, list[dict]] = {}
        # Set by shutdown(). Past this point nothing new may be scheduled: a
        # timer armed on a loop that is closing is a task that never runs.
        self._closing = False
        # Tasks currently inside _write. The write runs outside the lock, and
        # _take_batch has already cleared _timer_task by then - so without this,
        # a flush in flight is invisible to shutdown and dies with the loop.
        self._inflight: set[asyncio.Task] = set()

    async def add(self, request_log: RequestLog) -> None:
        """Add a request log to the buffer. Flushes when buffer is full."""
        async with self._lock:
            self._buffer.append(request_log)
            if len(self._buffer) < self._max_size:
                self._arm_timer()
                return
            batch = self._take_batch()
        # Outside the lock on purpose: see _write.
        await self._write(batch)

    async def shutdown(self) -> None:
        """Flush everything buffered, and wait for any flush already in flight.

        Named for the service lifecycle, but it is also how the test suites force
        a flush - and the buffer is a process-wide singleton. So `_closing` is
        held only for the duration of this call: leaving it set would make the
        first shutdown the last flush the process ever performs, and every entry
        accepted afterwards would sit in the buffer with no timer to write it.
        """
        self._closing = True
        try:
            await self._shutdown()
        finally:
            self._closing = False

    async def _shutdown(self) -> None:
        async with self._lock:
            self._cancel_timer()

        # A flush already in flight is finished rather than cancelled, and
        # waited for here. Cancelling it would only move its batch into a
        # backlog that nothing is left to flush - the same silent loss this
        # issue is about, relocated to shutdown. `_cancel_timer` above cannot
        # reach it either: a timer that got as far as writing has already had
        # its reference cleared by `_take_batch`.
        inflight = [task for task in self._inflight if task is not asyncio.current_task()]
        if inflight:
            try:
                await asyncio.gather(*inflight, return_exceptions=True)
            except asyncio.CancelledError:
                pass

        async with self._lock:
            batch = self._take_batch()
        await self._write(batch)

    def _arm_timer(self) -> None:
        """Start the age timer if one is not already running.

        Deliberately not re-armed per entry. Resetting it on every add made this
        an *idle* timer, with two costs: a stream that never pauses for
        flush_interval and never reaches max_size kept pushing the flush out, so
        entries could sit indefinitely; and it created one asyncio Task per
        request, which is the cost this buffer exists to avoid. Armed once, it
        bounds the age of the oldest entry instead.
        """
        if self._closing:
            return
        if self._timer_task is None or self._timer_task.done():
            self._timer_task = asyncio.create_task(self._timer())

    def _cancel_timer(self) -> None:
        """Stop the age timer - unless it is the task running right now.

        The self-cancellation guard is the fix for issue #180. ``_timer`` calls
        the flush and the flush stops the timer; when those are the same task,
        cancelling it delivers CancelledError at the next await (inside the
        write), where ``_timer`` swallows it - and the entries, already taken out
        of the buffer, are gone without a trace.
        """
        timer, self._timer_task = self._timer_task, None
        if timer is not None and timer is not asyncio.current_task() and not timer.done():
            timer.cancel()

    async def _timer(self) -> None:
        """Wait for flush_interval, then flush."""
        try:
            await asyncio.sleep(self._flush_interval)
            async with self._lock:
                batch = self._take_batch()
            await self._write(batch)
        except asyncio.CancelledError:
            pass
        finally:
            if self._timer_task is asyncio.current_task():
                self._timer_task = None

    def _take_batch(self) -> dict[str, list[dict]]:
        """Empty the buffer into per-database batches. Call with the lock held.

        Clears the timer reference here rather than after the write, so that an
        ``add`` arriving while the write is in flight sees no armed timer and
        arms a fresh one. Leaving the reference set across the write would let a
        concurrent add skip arming - and then the timer that is already on its
        way out clears it - which is how a buffer ends up holding entries with
        nothing scheduled to flush them.
        """
        self._cancel_timer()

        # Anything held back from a previous flush goes out first, ahead of the
        # entries buffered since.
        db_docs: dict[str, list[dict]] = self._pending
        self._pending = {}

        to_write, self._buffer = self._buffer, []
        for log in to_write:
            tenant_id = log.tenant_id
            targets = [f"{settings.DB_NAME_PREFIX}_commons"]
            if tenant_id:
                targets.append(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
            for db_name in targets:
                if db_name not in db_docs:
                    db_docs[db_name] = []
                # Coerced per target rather than once: `insert_many` stamps `_id`
                # into the document in place, so the two copies have to stay
                # separate objects.
                db_docs[db_name].append(_bson_safe(log.model_dump()))

        return db_docs

    def _pending_total(self) -> int:
        """Documents currently held back for a retry, across all databases."""
        return sum(len(docs) for docs in self._pending.values())

    def _keep_for_retry(self, failed: list[tuple[str, list[dict]]]) -> None:
        """Hold failed batches for the next flush, within MAX_PENDING_DOCS.

        The budget is shared out across the failing databases rather than handed
        to whichever one the loop reached first. An outage fails every target at
        once, and every entry goes to both the commons and the tenant database -
        so a first-come rule let commons take the whole allowance and dropped
        100% of the per-tenant trail, which is the copy an auditor reads.
        """
        if not failed:
            return
        budget = max(0, MAX_PENDING_DOCS - self._pending_total())
        share = budget // len(failed)
        for db_name, docs in failed:
            # `docs[-share:]` with share == 0 is the WHOLE list, not an empty one,
            # so a full backlog has to be spelled out rather than fall out of the
            # slice - and `max(1, ...)` would leak a document per database per
            # flush for as long as the outage lasts.
            keep = docs[-share:] if share > 0 else []  # most recent; see MAX_PENDING_DOCS
            if len(keep) < len(docs):
                logger.error(
                    f"Request log retry backlog is full ({MAX_PENDING_DOCS} documents); "
                    f"dropping {len(docs) - len(keep)} of {len(docs)} documents for {db_name}. "
                    "The audit trail has a hole for this window."
                )
            if keep:
                # Never leave an empty list behind: the next flush would hand it
                # to insert_many, which rejects an empty batch with a TypeError
                # and fails that whole target for the flush.
                self._pending.setdefault(db_name, []).extend(keep)
        # Traffic may stop before the next add, so the retry needs its own wake-up.
        self._arm_timer()

    async def _write(self, db_docs: dict[str, list[dict]]) -> None:
        """Write per-database batches. Runs OUTSIDE the lock.

        Outside on purpose: this awaits MongoDB, and holding the lock across that
        would make every concurrent request wait on the audit log it is only
        supposed to leave a note in. With an unreachable backend that is a
        server-selection timeout per flush, so the logging of a request would
        stall the requests - the buffer taking down the service it audits.

        Retries are safe to repeat: ``insert_many`` stamps ``_id`` into the
        documents in place, so a document written before an interruption is
        refused as a duplicate on the way back rather than stored twice.
        """
        if not db_docs:
            return

        task = asyncio.current_task()
        if task is not None:
            self._inflight.add(task)
        try:
            await self._write_batches(db_docs)
        finally:
            if task is not None:
                self._inflight.discard(task)

    async def _rewrite_individually(
        self, db_name: str, collection, docs: list[dict], batch_error: BaseException
    ) -> list[tuple[str, list[dict]]]:
        """Offer a batch-refused set of documents again, one at a time.

        The `BulkWriteError` branch can say *"the rest were written"* because
        the server answered per document. When the driver refuses the batch
        before the wire - a document BSON cannot encode (issue #210) - there is
        no per-document answer, and the batch becomes all-or-nothing: one bad
        document discards up to `max_size` unrelated audit records. Writing them
        individually restores the distinction the bulk error already had, and
        bounds the loss to the entries that are genuinely unwritable, naming
        each one.

        Args:
            db_name: Target database, for the report
            collection: The request-log collection to write to
            docs: The documents the batch write refused
            batch_error: Why the batch was refused, for the report

        Returns:
            `[(db_name, docs)]` for documents worth another flush, else `[]`
        """
        logger.warning(
            f"Request log batch of {len(docs)} documents was refused by {db_name} as a batch "
            f"({batch_error}); rewriting them individually so one document does not discard the rest."
        )
        lost: list[tuple[dict, BaseException]] = []
        retry: list[dict] = []
        written = 0
        for doc in docs:
            try:
                await collection.insert_one(doc)
                written += 1
            except DuplicateKeyError:
                # `insert_many` stamps `_id` in place, so a document the server
                # did take before the batch failed comes back as a duplicate.
                # It is in the database; that is the outcome we wanted.
                written += 1
            except Exception as e:
                if _is_transient(e):
                    retry.append(doc)
                else:
                    lost.append((doc, e))
        for doc, error in lost:
            logger.error(f"Request log entry cannot be written to {db_name} and is lost: {_describe(doc)}: {error}")
        logger.info(
            f"Request log rewrite for {db_name}: {written} written, "
            f"{len(retry)} kept for the next flush, {len(lost)} lost."
        )
        return [(db_name, retry)] if retry else []

    async def _write_batches(self, db_docs: dict[str, list[dict]]) -> None:
        """The write itself; see _write for why it runs outside the lock."""
        items = list(db_docs.items())
        failed: list[tuple[str, list[dict]]] = []
        attempted = 0
        try:
            for db_name, docs in items:
                if not docs:
                    attempted += 1
                    continue
                collection = None
                try:
                    database = await db_helper.get_db_async(db_name)
                    collection = database[settings.DB_COLLECTION_NAME_REQUEST_LOG]
                    await collection.insert_many(docs, ordered=False)
                    logger.debug(f"Flushed {len(docs)} request logs to {db_name}")
                except BulkWriteError as e:
                    # The server answered and refused specific documents (a
                    # duplicate key, an oversized document). With ordered=False
                    # the rest were written, and repeating the batch would only
                    # repeat the refusal.
                    refused = len(e.details.get("writeErrors", [])) if isinstance(e.details, dict) else len(docs)
                    logger.error(
                        f"Request log write to {db_name} refused {refused} of {len(docs)} documents "
                        f"(the rest were written): {e}. Not retried.",
                        exc_info=True,
                    )
                except Exception as e:
                    if _is_transient(e):
                        # The backend could not be reached, so the batch is worth
                        # keeping: a restart or a failover ends, and the next
                        # flush carries it.
                        failed.append((db_name, docs))
                        logger.error(
                            f"Request log backend unreachable for {db_name}: {e}. "
                            f"Kept {len(docs)} documents for the next flush.",
                            exc_info=True,
                        )
                    elif collection is not None and len(docs) > 1:
                        # The batch was refused as a batch, with no per-document
                        # answer to go on - so the documents that were fine are
                        # offered again one at a time, and only what actually
                        # fails is lost (issue #210).
                        failed.extend(await self._rewrite_individually(db_name, collection, docs, e))
                    else:
                        # Either there was no collection to write to (the failure
                        # was in reaching the database, and repeating it per
                        # document would only repeat it 100 times), or the batch
                        # was one document and has already had its chance.
                        logger.error(
                            f"Request log write to {db_name} failed for {len(docs)} documents "
                            f"and cannot be repeated: {e}. Those entries are lost.",
                            exc_info=True,
                        )
                attempted += 1
        except asyncio.CancelledError:
            # A size-triggered flush runs on the request task that filled the
            # buffer, so a client disconnect cancels it - and the batch it is
            # carrying belongs to every other request in the window, not to that
            # client. Keep what was not written, then let the cancellation stand.
            # From the batch that was in flight to the end. A slice rather
            # than an index: `attempted` is only ever < len(items) here, but an
            # IndexError raised inside a cancellation handler would skip the
            # salvage entirely, which is too expensive a way to find out.
            failed.extend(items[attempted:])
            self._keep_for_retry(failed)
            logger.error(
                f"Request log flush was cancelled mid-write; kept {sum(len(d) for _, d in failed)} "
                "documents for the next flush."
            )
            raise

        self._keep_for_retry(failed)


# Module-level singleton
_buffer: RequestLogBuffer | None = None


def get_request_log_buffer() -> RequestLogBuffer:
    """Get or create the singleton RequestLogBuffer instance.

    Configuration via environment variables:
        REQUEST_LOG_BUFFER_SIZE: Max buffer size before flush (default: 100)
        REQUEST_LOG_FLUSH_INTERVAL: Age of the oldest entry before a flush, in
            seconds (default: 5.0)
    """
    global _buffer
    if _buffer is None:
        import os

        max_size = int(os.environ.get("REQUEST_LOG_BUFFER_SIZE", "100"))
        flush_interval = float(os.environ.get("REQUEST_LOG_FLUSH_INTERVAL", "5.0"))
        _buffer = RequestLogBuffer(max_size=max_size, flush_interval=flush_interval)
        logger.info(f"RequestLogBuffer initialized: max_size={max_size}, flush_interval={flush_interval}s")
    return _buffer

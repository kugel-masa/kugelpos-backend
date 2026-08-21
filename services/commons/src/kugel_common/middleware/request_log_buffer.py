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
"""

import asyncio
from logging import getLogger
from typing import List

from pymongo.errors import BulkWriteError, ConnectionFailure

from kugel_common.database import database as db_helper
from kugel_common.models.documents.request_log_document import RequestLog
from kugel_common.config.settings import settings

logger = getLogger(__name__)

# Ceiling on documents held back for a retry. A backend that stays unreachable
# must not turn the audit buffer into a memory leak, so the backlog is a sliding
# window of the most recent documents: during an ongoing outage those are the
# ones an operator is looking for, and no bound can keep the trail complete.
MAX_PENDING_DOCS = 1000


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
        """Flush remaining buffer on service shutdown."""
        async with self._lock:
            self._cancel_timer()
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
                db_docs[db_name].append(log.model_dump())

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

        items = list(db_docs.items())
        failed: list[tuple[str, list[dict]]] = []
        attempted = 0
        try:
            for db_name, docs in items:
                try:
                    database = await db_helper.get_db_async(db_name)
                    collection = database[settings.DB_COLLECTION_NAME_REQUEST_LOG]
                    await collection.insert_many(docs, ordered=False)
                    logger.debug(f"Flushed {len(docs)} request logs to {db_name}")
                except ConnectionFailure as e:
                    # The backend could not be reached, so the batch is worth
                    # keeping: a restart or a failover ends, and the next flush
                    # carries it.
                    failed.append((db_name, docs))
                    logger.error(
                        f"Request log backend unreachable for {db_name}: {e}. "
                        f"Kept {len(docs)} documents for the next flush.",
                        exc_info=True,
                    )
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
                    logger.error(
                        f"Failed to flush {len(docs)} request logs to {db_name}: {e}",
                        exc_info=True,
                    )
                attempted += 1
        except asyncio.CancelledError:
            # A size-triggered flush runs on the request task that filled the
            # buffer, so a client disconnect cancels it - and the batch it is
            # carrying belongs to every other request in the window, not to that
            # client. Keep what was not written, then let the cancellation stand.
            failed.append((items[attempted][0], items[attempted][1]))
            failed.extend(items[attempted + 1 :])
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

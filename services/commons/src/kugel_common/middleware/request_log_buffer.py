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
        self._pending: dict[str, list[dict]] = {}

    async def add(self, request_log: RequestLog) -> None:
        """Add a request log to the buffer. Flushes when buffer is full."""
        async with self._lock:
            self._buffer.append(request_log)
            if len(self._buffer) >= self._max_size:
                await self._flush_unlocked()
            else:
                self._arm_timer()

    async def shutdown(self) -> None:
        """Flush remaining buffer on service shutdown."""
        async with self._lock:
            self._cancel_timer()
            await self._flush_unlocked()

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
                await self._flush_unlocked()
        except asyncio.CancelledError:
            pass
        finally:
            if self._timer_task is asyncio.current_task():
                self._timer_task = None

    def _pending_total(self) -> int:
        """Documents currently held back for a retry, across all databases."""
        return sum(len(docs) for docs in self._pending.values())

    def _keep_for_retry(self, db_name: str, docs: list[dict]) -> None:
        """Hold a failed batch for the next flush, within MAX_PENDING_DOCS."""
        room = MAX_PENDING_DOCS - self._pending_total()
        if len(docs) > room:
            dropped = len(docs) - max(room, 0)
            logger.error(
                f"Request log retry backlog is full ({MAX_PENDING_DOCS} documents); "
                f"dropping {dropped} of {len(docs)} entries for {db_name}. "
                "The audit trail has a hole for this window."
            )
            if room <= 0:
                return
            docs = docs[-room:]  # keep the most recent; see MAX_PENDING_DOCS
        self._pending.setdefault(db_name, []).extend(docs)

    async def _flush_unlocked(self) -> None:
        """Write buffered logs to MongoDB. Must be called with _lock held."""
        if not self._buffer and not self._pending:
            return

        to_write = self._buffer
        self._buffer = []
        self._cancel_timer()

        # Anything held back from a previous flush goes out first, ahead of the
        # entries buffered since.
        db_docs: dict[str, list[dict]] = {db_name: docs for db_name, docs in self._pending.items()}
        self._pending = {}

        # Group by target database
        for log in to_write:
            tenant_id = log.tenant_id
            targets = [f"{settings.DB_NAME_PREFIX}_commons"]
            if tenant_id:
                targets.append(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
            for db_name in targets:
                if db_name not in db_docs:
                    db_docs[db_name] = []
                db_docs[db_name].append(log.model_dump())

        # Batch insert per database
        for db_name, docs in db_docs.items():
            try:
                database = await db_helper.get_db_async(db_name)
                collection = database[settings.DB_COLLECTION_NAME_REQUEST_LOG]
                await collection.insert_many(docs, ordered=False)
                logger.debug(f"Flushed {len(docs)} request logs to {db_name}")
            except ConnectionFailure as e:
                # The backend could not be reached, so the batch is worth keeping:
                # a restart or a failover ends, and the next flush carries it.
                # Retrying a batch a network error interrupted mid-write can
                # duplicate documents - at-least-once is the right trade for an
                # audit trail against losing the window entirely.
                self._keep_for_retry(db_name, docs)
                logger.error(
                    f"Request log backend unreachable for {db_name}: {e}. "
                    f"Kept {len(docs)} documents for the next flush.",
                    exc_info=True,
                )
            except BulkWriteError as e:
                # The server answered and refused specific documents (a duplicate
                # key, an oversized document). With ordered=False the rest were
                # written, and repeating the batch would only repeat the refusal.
                failed = len(e.details.get("writeErrors", [])) if isinstance(e.details, dict) else len(docs)
                logger.error(
                    f"Request log write to {db_name} refused {failed} of {len(docs)} documents "
                    f"(the rest were written): {e}. Not retried; those entries are lost.",
                    exc_info=True,
                )
            except Exception as e:
                logger.error(
                    f"Failed to flush {len(docs)} request logs to {db_name}: {e}",
                    exc_info=True,
                )


# Module-level singleton
_buffer: RequestLogBuffer | None = None


def get_request_log_buffer() -> RequestLogBuffer:
    """Get or create the singleton RequestLogBuffer instance.

    Configuration via environment variables:
        REQUEST_LOG_BUFFER_SIZE: Max buffer size before flush (default: 100)
        REQUEST_LOG_FLUSH_INTERVAL: Idle flush interval in seconds (default: 5.0)
    """
    global _buffer
    if _buffer is None:
        import os
        max_size = int(os.environ.get("REQUEST_LOG_BUFFER_SIZE", "100"))
        flush_interval = float(os.environ.get("REQUEST_LOG_FLUSH_INTERVAL", "5.0"))
        _buffer = RequestLogBuffer(max_size=max_size, flush_interval=flush_interval)
        logger.info(f"RequestLogBuffer initialized: max_size={max_size}, flush_interval={flush_interval}s")
    return _buffer

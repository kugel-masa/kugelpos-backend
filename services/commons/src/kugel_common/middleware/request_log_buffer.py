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
- No new requests for flush_interval seconds (default: 5.0)
- Service shutdown (via shutdown() method)
"""
import asyncio
from logging import getLogger
from typing import List

from kugel_common.database import database as db_helper
from kugel_common.models.documents.request_log_document import RequestLog
from kugel_common.config.settings import settings

logger = getLogger(__name__)


class RequestLogBuffer:
    """Batches RequestLog documents and flushes them to MongoDB via insert_many."""

    def __init__(self, max_size: int = 100, flush_interval: float = 5.0):
        self._buffer: List[RequestLog] = []
        self._max_size = max_size
        self._flush_interval = flush_interval
        self._timer_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def add(self, request_log: RequestLog) -> None:
        """Add a request log to the buffer. Flushes when buffer is full."""
        async with self._lock:
            self._buffer.append(request_log)
            self._reset_timer()
            if len(self._buffer) >= self._max_size:
                await self._flush_unlocked()

    async def shutdown(self) -> None:
        """Flush remaining buffer on service shutdown."""
        async with self._lock:
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
                self._timer_task = None
            await self._flush_unlocked()

    def _reset_timer(self) -> None:
        """Reset the idle flush timer."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._timer())

    async def _timer(self) -> None:
        """Wait for flush_interval, then flush."""
        try:
            await asyncio.sleep(self._flush_interval)
            async with self._lock:
                await self._flush_unlocked()
        except asyncio.CancelledError:
            pass

    async def _flush_unlocked(self) -> None:
        """Write buffered logs to MongoDB. Must be called with _lock held."""
        if not self._buffer:
            return

        to_write = self._buffer
        self._buffer = []

        # Cancel timer since we're flushing now
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None

        # Group by target database
        db_docs: dict[str, list[dict]] = {}
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
            except Exception as e:
                logger.error(
                    f"Failed to flush {len(docs)} request logs to {db_name}: {e}",
                    exc_info=True,
                )


# Module-level singleton
_buffer: RequestLogBuffer | None = None


def get_request_log_buffer() -> RequestLogBuffer:
    """Get or create the singleton RequestLogBuffer instance."""
    global _buffer
    if _buffer is None:
        _buffer = RequestLogBuffer()
    return _buffer

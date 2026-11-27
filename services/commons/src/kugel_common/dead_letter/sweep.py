# Copyright 2026 masa@kugel
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
The periodic sweep of the dead-letter records (R-14).

Every DEAD_LETTER_SWEEP_INTERVAL_SECONDS, over every tenant database of the
service:

1. A failing record whose last failure is older than
   DEAD_LETTER_STALE_FAILING_SECONDS is past every redelivery. If the event was
   processed after all (its id is in the state store), the record is deleted;
   otherwise the sidecar gave up before the subscriber did (deliveries that never
   reached it were not counted) and the record becomes pending and is notified.
2. A pending record still not notified is claimed and notified again, up to
   MAX_NOTIFY_ATTEMPTS times.

Every write is conditional, so replicas sweeping at once do not double up. A
failure is logged and never stops the service.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from logging import getLogger
from typing import Optional

from kugel_common.config.settings import settings
from kugel_common.database import database as db_helper
from kugel_common.database.index_startup import tenants_from_db_names
from kugel_common.dead_letter import alerts
from kugel_common.dead_letter.document import SWEEP_BATCH
from kugel_common.dead_letter.repository import DeadLetterRepository, utc_now

logger = getLogger(__name__)

# Answers whether an event id is in the state store: True, False, or None when
# the store could not be asked (the record is then left for the next sweep).
IsProcessed = Callable[[str], Awaitable[Optional[bool]]]


class DeadLetterSweeper:
    def __init__(
        self,
        *,
        service: str,
        db_name_prefix: str,
        is_processed: IsProcessed,
        interval_seconds: Optional[int] = None,
        stale_seconds: Optional[int] = None,
        notify_retry_after_seconds: Optional[int] = None,
        client_getter: Optional[Callable[[], Awaitable]] = None,
    ):
        self.service = service
        self.db_name_prefix = db_name_prefix
        self.is_processed = is_processed
        self.interval_seconds = interval_seconds or settings.DEAD_LETTER_SWEEP_INTERVAL_SECONDS
        self.stale_seconds = stale_seconds or settings.DEAD_LETTER_STALE_FAILING_SECONDS
        self.notify_retry_after_seconds = notify_retry_after_seconds or settings.DEAD_LETTER_NOTIFY_RETRY_AFTER_SECONDS
        self.client_getter = client_getter or db_helper.get_client_async
        self._task: Optional[asyncio.Task] = None

    async def run_once(self) -> dict:
        """One pass over every tenant. Returns counts, for the log and the tests."""
        totals = {"deleted": 0, "promoted": 0, "renotified": 0}
        try:
            client = await self.client_getter()
            tenants = tenants_from_db_names(await client.list_database_names(), self.db_name_prefix)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[{self.service}] Dead-letter sweep skipped: could not list databases ({type(e).__name__})")
            return totals
        for tenant_id in tenants:
            try:
                db = await db_helper.get_db_async(f"{self.db_name_prefix}_{tenant_id}")
                counts = await self.sweep_tenant(db)
                for key, value in counts.items():
                    totals[key] += value
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - one tenant must not stop the others
                logger.warning(f"[{self.service}] Dead-letter sweep failed for tenant {tenant_id} ({type(e).__name__})")
        if any(totals.values()):
            logger.info(f"[{self.service}] Dead-letter sweep: {totals}")
        return totals

    async def sweep_tenant(self, db) -> dict:
        repo = DeadLetterRepository(db)
        counts = {"deleted": 0, "promoted": 0, "renotified": 0}

        older_than = utc_now() - timedelta(seconds=self.stale_seconds)
        for record in await repo.find_stale_failing(older_than, SWEEP_BATCH):
            event_id = record["_id"]
            processed = await self._is_processed(event_id)
            if processed is None:
                continue
            if processed:
                if await repo.delete_failing(event_id, record["last_failed_at"]):
                    counts["deleted"] += 1
                continue
            promoted = await repo.promote_stale_failing(event_id, record["last_failed_at"])
            if promoted is None:
                continue
            counts["promoted"] += 1
            logger.warning(
                f"[{self.service}] Stranded failing record made pending (retries ran out before the subscriber "
                f"gave up). event_id={event_id} failures={promoted.get('failure_count')}"
            )
            promoted.pop("message", None)
            if await alerts.notify_new_pending(db, self.service, promoted, via_sweep=True):
                await repo.set_notified(event_id)

        for record in await repo.find_unnotified(self.notify_retry_after_seconds, SWEEP_BATCH):
            claimed = await repo.claim_notify(record["_id"], self.notify_retry_after_seconds)
            if claimed is None:
                continue
            if await alerts.send(alerts.format_record(self.service, claimed), self.service):
                await repo.set_notified(record["_id"])
                counts["renotified"] += 1
        return counts

    async def _is_processed(self, event_id: str) -> Optional[bool]:
        try:
            return await self.is_processed(event_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[{self.service}] State store not asked for {event_id} ({type(e).__name__})")
            return None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[{self.service}] Dead-letter sweep failed ({type(e).__name__})")

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name=f"{self.service}-dead-letter-sweep")
        return self._task

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

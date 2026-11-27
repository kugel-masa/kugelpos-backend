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
Reads and writes of the dead-letter records (#230).

Every write that decides something is a single conditional update, so two
workers, two replicas or a duplicate delivery cannot both win. Values that come
from outside (the event, its summary, the error text, the topic) go into
aggregation-pipeline updates wrapped in ``$literal``: there a string starting
with "$" is read as a field path and a key starting with "$" as an operator.
"""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from kugel_common.database import database as db_helper
from kugel_common.dead_letter.document import (
    ALERT_COLLECTION,
    COLLECTION,
    COUNTING_STATES,
    FAILING_RETENTION,
    MAX_NOTIFY_ATTEMPTS,
    NOTIFY_LEASE,
    REPLAY_LEASE,
    RESOLVED_RETENTION,
    STATE_DISCARDED,
    STATE_FAILING,
    STATE_PENDING,
    STATE_REPLAYED,
    STATE_REPLAYING,
)

logger = getLogger(__name__)

NOW = "$$NOW"
_RESOLVED = (STATE_REPLAYED, STATE_DISCARDED)
_NEW_OR_FAILING = ("none", STATE_FAILING)


def _lit(value: Any) -> dict:
    return {"$literal": value}


def _days_from_now(days: int) -> dict:
    return {"$dateAdd": {"startDate": NOW, "unit": "day", "amount": days}}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def failure_pipeline(
    *,
    event_id: str,
    tenant_id: Optional[str],
    service: str,
    topic: str,
    message: dict,
    summary: dict,
    last_error: str,
    give_up_after: int,
) -> list[dict]:
    """
    The update a failure makes (data-model, "処理の失敗").

    Exposed for the unit tests, which check its shape; the behaviour is checked
    against a real MongoDB in the integration tests.
    """
    prev = "$_dl_prev_state"
    give_up = "$_dl_give_up"
    rewrite_message = {
        "$or": [
            {"$in": [prev, ["none", *_RESOLVED]]},
            {"$eq": [{"$ifNull": ["$message", None]}, None]},
        ]
    }
    return [
        {
            "$set": {
                "_dl_prev_state": {"$ifNull": ["$state", "none"]},
                "_dl_prev_ep": {"$ifNull": ["$episode_failure_count", 0]},
            }
        },
        {
            "$set": {
                "_dl_counting": {"$in": [prev, list(COUNTING_STATES)]},
            }
        },
        {
            "$set": {
                "_dl_give_up": {"$and": ["$_dl_counting", {"$gte": [{"$add": ["$_dl_prev_ep", 1]}, give_up_after]}]},
                "episode_failure_count": {"$cond": ["$_dl_counting", {"$add": ["$_dl_prev_ep", 1]}, "$_dl_prev_ep"]},
            }
        },
        {
            "$set": {
                "event_id": _lit(event_id),
                "tenant_id": {"$ifNull": ["$tenant_id", _lit(tenant_id)]},
                "service": _lit(service),
                "topic": {"$ifNull": ["$topic", _lit(topic)]},
                "message": {"$cond": [rewrite_message, _lit(message), "$message"]},
                "summary": {"$cond": [rewrite_message, _lit(summary), {"$ifNull": ["$summary", _lit(summary)]}]},
                "last_error": _lit(last_error),
                "last_failed_at": NOW,
                "first_failed_at": {"$ifNull": ["$first_failed_at", NOW]},
                "failure_count": {"$add": [{"$ifNull": ["$failure_count", 0]}, 1]},
                "dead_count": {"$ifNull": ["$dead_count", 0]},
                "notify_attempts": {"$ifNull": ["$notify_attempts", 0]},
                "created_at": {"$ifNull": ["$created_at", NOW]},
                "updated_at": NOW,
            }
        },
        {
            "$set": {
                "state": {
                    "$switch": {
                        "branches": [
                            {"case": give_up, "then": STATE_PENDING},
                            {"case": {"$in": [prev, list(_NEW_OR_FAILING)]}, "then": STATE_FAILING},
                        ],
                        "default": prev,
                    }
                },
                "purge_at": {
                    "$switch": {
                        "branches": [
                            {"case": give_up, "then": None},
                            {
                                "case": {"$in": [prev, list(_NEW_OR_FAILING)]},
                                "then": _days_from_now(FAILING_RETENTION.days),
                            },
                            # Counting again after a resolution: not purged mid-count
                            {
                                "case": {"$in": [prev, list(_RESOLVED)]},
                                "then": {
                                    "$max": [{"$ifNull": ["$purge_at", NOW]}, _days_from_now(FAILING_RETENTION.days)]
                                },
                            },
                        ],
                        "default": {"$ifNull": ["$purge_at", None]},
                    }
                },
                "dead_count": {"$cond": [give_up, {"$add": ["$dead_count", 1]}, "$dead_count"]},
                "first_dead_at": {
                    "$cond": [give_up, {"$ifNull": ["$first_dead_at", NOW]}, {"$ifNull": ["$first_dead_at", None]}]
                },
                "last_dead_at": {"$cond": [give_up, NOW, {"$ifNull": ["$last_dead_at", None]}]},
                "notified_at": {"$cond": [give_up, None, {"$ifNull": ["$notified_at", None]}]},
                "notify_claimed_at": {"$cond": [give_up, None, {"$ifNull": ["$notify_claimed_at", None]}]},
                "notify_attempts": {"$cond": [give_up, 0, "$notify_attempts"]},
                "resolved_at": {"$cond": [give_up, None, {"$ifNull": ["$resolved_at", None]}]},
                "resolved_by": {"$cond": [give_up, None, {"$ifNull": ["$resolved_by", None]}]},
                "resolution_note": {"$cond": [give_up, None, {"$ifNull": ["$resolution_note", None]}]},
                "replay_claim_id": {"$cond": [give_up, None, {"$ifNull": ["$replay_claim_id", None]}]},
                "replay_claimed_at": {"$cond": [give_up, None, {"$ifNull": ["$replay_claimed_at", None]}]},
            }
        },
        {"$unset": ["_dl_prev_state", "_dl_prev_ep", "_dl_counting", "_dl_give_up"]},
    ]


def promote_pipeline() -> list[dict]:
    """A stranded failing record becomes pending (the sweep, R-14)."""
    return [
        {
            "$set": {
                "state": STATE_PENDING,
                "purge_at": None,
                "dead_count": {"$add": [{"$ifNull": ["$dead_count", 0]}, 1]},
                "first_dead_at": {"$ifNull": ["$first_dead_at", NOW]},
                "last_dead_at": NOW,
                "notified_at": None,
                "notify_claimed_at": None,
                "notify_attempts": 0,
                "updated_at": NOW,
            }
        }
    ]


class DeadLetterRepository:
    """The dead-letter records of one service in one tenant database."""

    def __init__(self, db: AsyncDatabase):
        self.db = db
        self.collection = db[COLLECTION]

    # -- failures (R-4) -------------------------------------------------------

    async def record_failure(
        self,
        *,
        event_id: str,
        tenant_id: Optional[str],
        service: str,
        topic: str,
        message: dict,
        summary: dict,
        last_error: str,
        give_up_after: int,
    ) -> Optional[dict]:
        """
        Count one failure. Returns the record as it was before (None when new).

        A duplicate key means two workers inserted the first document at once;
        the update is tried once more, and then finds the other's document.
        """
        pipeline = failure_pipeline(
            event_id=event_id,
            tenant_id=tenant_id,
            service=service,
            topic=topic,
            message=message,
            summary=summary,
            last_error=last_error,
            give_up_after=give_up_after,
        )
        for attempt in (1, 2):
            try:
                return await self.collection.find_one_and_update(
                    {"_id": event_id}, pipeline, upsert=True, return_document=ReturnDocument.BEFORE
                )
            except DuplicateKeyError:
                if attempt == 2:
                    raise
        return None  # unreachable

    async def set_notified(self, event_id: str) -> None:
        await self.collection.update_one(
            {"_id": event_id, "state": STATE_PENDING},
            {"$set": {"notified_at": utc_now(), "notify_claimed_at": None}},
        )

    # -- the sweep (R-14) -----------------------------------------------------

    async def find_stale_failing(self, older_than: datetime, limit: int) -> list[dict]:
        cursor = self.collection.find(
            {"state": STATE_FAILING, "last_failed_at": {"$lt": older_than}},
            projection={"message": False},
            limit=limit,
        )
        return [doc async for doc in cursor]

    async def promote_stale_failing(self, event_id: str, last_failed_at: datetime) -> Optional[dict]:
        """Pending, unless another failure or worker got there first."""
        return await self.collection.find_one_and_update(
            {"_id": event_id, "state": STATE_FAILING, "last_failed_at": last_failed_at},
            promote_pipeline(),
            return_document=ReturnDocument.AFTER,
        )

    async def delete_failing(self, event_id: str, last_failed_at: datetime) -> bool:
        result = await self.collection.delete_one(
            {"_id": event_id, "state": STATE_FAILING, "last_failed_at": last_failed_at}
        )
        return result.deleted_count == 1

    def _unnotified_filter(self, now: datetime, retry_after_seconds: int) -> dict:
        return {
            "state": STATE_PENDING,
            "notified_at": None,
            "last_dead_at": {"$lt": now - timedelta(seconds=retry_after_seconds)},
            "notify_attempts": {"$lt": MAX_NOTIFY_ATTEMPTS},
            "$or": [{"notify_claimed_at": None}, {"notify_claimed_at": {"$lt": now - NOTIFY_LEASE}}],
        }

    async def find_unnotified(self, retry_after_seconds: int, limit: int) -> list[dict]:
        cursor = self.collection.find(
            self._unnotified_filter(utc_now(), retry_after_seconds),
            projection={"message": False},
            limit=limit,
        )
        return [doc async for doc in cursor]

    async def claim_notify(self, event_id: str, retry_after_seconds: int) -> Optional[dict]:
        now = utc_now()
        return await self.collection.find_one_and_update(
            {"_id": event_id, **self._unnotified_filter(now, retry_after_seconds)},
            {"$set": {"notify_claimed_at": now}, "$inc": {"notify_attempts": 1}},
            projection={"message": False},
            return_document=ReturnDocument.AFTER,
        )

    # -- replay (R-7) ---------------------------------------------------------

    async def claim_replay(self, event_id: str, claim_id: str) -> Optional[dict]:
        now = utc_now()
        return await self.collection.find_one_and_update(
            {
                "_id": event_id,
                "$or": [
                    {"state": STATE_PENDING},
                    {"state": STATE_REPLAYING, "replay_claimed_at": {"$lt": now - REPLAY_LEASE}},
                ],
            },
            {
                "$set": {
                    "state": STATE_REPLAYING,
                    "replay_claim_id": claim_id,
                    "replay_claimed_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def finish_replay(
        self,
        event_id: str,
        claim_id: str,
        *,
        state: str,
        resolved_by: Optional[str] = None,
        resolution_note: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> bool:
        """Write a replay's result; only the holder of the claim may (R-7)."""
        now = utc_now()
        claim = {"_id": event_id, "state": STATE_REPLAYING, "replay_claim_id": claim_id}
        if state == STATE_PENDING:
            update = {
                "$set": {
                    "state": STATE_PENDING,
                    "last_error": last_error,
                    "last_failed_at": now,
                    "replay_claim_id": None,
                    "replay_claimed_at": None,
                    "updated_at": now,
                },
                "$inc": {"failure_count": 1},
            }
        else:
            update = {
                "$set": {
                    "state": state,
                    "resolved_at": now,
                    "resolved_by": resolved_by,
                    "resolution_note": resolution_note,
                    "episode_failure_count": 0,
                    "purge_at": now + RESOLVED_RETENTION,
                    "replay_claim_id": None,
                    "replay_claimed_at": None,
                    "updated_at": now,
                }
            }
        result = await self.collection.update_one(claim, update)
        return result.modified_count == 1

    # -- discard --------------------------------------------------------------

    async def discard(self, event_id: str, user: str, reason: str) -> Optional[dict]:
        now = utc_now()
        return await self.collection.find_one_and_update(
            {"_id": event_id, "state": STATE_PENDING},
            {
                "$set": {
                    "state": STATE_DISCARDED,
                    "resolved_at": now,
                    "resolved_by": user,
                    "resolution_note": reason,
                    "episode_failure_count": 0,
                    "purge_at": now + RESOLVED_RETENTION,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    # -- reads ----------------------------------------------------------------

    async def get(self, event_id: str, with_message: bool = True) -> Optional[dict]:
        projection = None if with_message else {"message": False}
        return await self.collection.find_one({"_id": event_id}, projection=projection)

    async def list(
        self,
        *,
        states: list[str],
        topic: Optional[str] = None,
        notified: Optional[bool] = None,
        dead_from: Optional[datetime] = None,
        dead_to: Optional[datetime] = None,
        limit: int = 50,
        page: int = 1,
    ) -> tuple[list[dict], int]:
        query: dict = {"state": {"$in": states}}
        if topic:
            query["topic"] = topic
        if notified is False:
            query["notified_at"] = None
        elif notified is True:
            query["notified_at"] = {"$ne": None}
        if dead_from or dead_to:
            window: dict = {}
            if dead_from:
                window["$gte"] = dead_from
            if dead_to:
                window["$lte"] = dead_to
            query["last_dead_at"] = window
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query, projection={"message": False})
            .sort([("last_dead_at", DESCENDING), ("_id", ASCENDING)])
            .skip((page - 1) * limit)
            .limit(limit)
        )
        return [doc async for doc in cursor], total


# -- indexes ------------------------------------------------------------------

DEAD_LETTER_INDEXES = [
    {"keys": {"state": 1, "last_dead_at": -1}, "unique": False},
    {"keys": {"topic": 1, "state": 1, "last_dead_at": -1}, "unique": False},
    {"keys": {"state": 1, "last_failed_at": 1}, "unique": False},
    {"keys": {"state": 1, "notified_at": 1, "last_dead_at": 1}, "unique": False},
    {"keys": {"purge_at": 1}, "unique": False, "expireAfterSeconds": 0},
]


async def create_dead_letter_collections_async(db_name: str) -> None:
    """
    The collections and indexes a subscriber's tenant database needs (data-model).

    For the services' ``database_setup``. The record is keyed by ``_id``, which
    MongoDB indexes uniquely by itself.
    """
    await db_helper.create_collection_with_indexes_async(
        db_name=db_name,
        collection_name=COLLECTION,
        index_keys_list=DEAD_LETTER_INDEXES,
        index_name=COLLECTION + "_index",
    )
    db = await db_helper.get_db_async(db_name)
    await db_helper.create_collection_async(collection_name=ALERT_COLLECTION, db=db)

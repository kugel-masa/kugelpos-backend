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
Notifications for records that became pending (R-5, R-5a).

A five-minute window per tenant and service (one ``dead_letter_alert``
document): up to nine records are notified one by one, the tenth sends one
summary, the rest are counted and mentioned by the next window's first notice.
The window moves in a single pipeline ``find_one_and_update``, so concurrent
workers count each record once.
"""

import asyncio
from logging import getLogger
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from kugel_common.dead_letter.document import (
    ALERT_COLLECTION,
    ALERT_WINDOW_ID,
    SLACK_TIMEOUT_SECONDS,
    give_up_after_failures,
)

logger = getLogger(__name__)

WINDOW_SECONDS = 300
INDIVIDUAL_LIMIT = 9
SUMMARY_AT = 10


def window_pipeline(topic: str) -> list[dict]:
    """The update that counts one record into the window."""
    one_topic = {"$arrayToObject": [[{"k": {"$literal": topic}, "v": 1}]]}
    topic_plus_one = {
        "$arrayToObject": [
            [
                {
                    "k": {"$literal": topic},
                    "v": {
                        "$add": [
                            {
                                "$ifNull": [
                                    {
                                        "$getField": {
                                            "field": {"$literal": topic},
                                            "input": {"$ifNull": ["$topics", {}]},
                                        }
                                    },
                                    0,
                                ]
                            },
                            1,
                        ]
                    },
                }
            ]
        ]
    }
    return [
        {
            "$set": {
                "_w_new": {
                    "$or": [
                        {"$eq": [{"$ifNull": ["$window_started_at", None]}, None]},
                        {
                            "$lt": [
                                "$window_started_at",
                                {"$dateSubtract": {"startDate": "$$NOW", "unit": "second", "amount": WINDOW_SECONDS}},
                            ]
                        },
                    ]
                }
            }
        },
        {
            "$set": {
                "carried_suppressed": {
                    "$cond": ["$_w_new", {"$ifNull": ["$suppressed", 0]}, {"$ifNull": ["$carried_suppressed", 0]}]
                },
                "window_started_at": {"$cond": ["$_w_new", "$$NOW", "$window_started_at"]},
                "count": {"$cond": ["$_w_new", 1, {"$add": [{"$ifNull": ["$count", 0]}, 1]}]},
                "topics": {
                    "$cond": ["$_w_new", one_topic, {"$mergeObjects": [{"$ifNull": ["$topics", {}]}, topic_plus_one]}]
                },
            }
        },
        {
            "$set": {
                "suppressed": {
                    "$cond": [
                        "$_w_new",
                        0,
                        {
                            "$cond": [
                                {"$gt": ["$count", SUMMARY_AT]},
                                {"$add": [{"$ifNull": ["$suppressed", 0]}, 1]},
                                {"$ifNull": ["$suppressed", 0]},
                            ]
                        },
                    ]
                }
            }
        },
        {"$unset": ["_w_new"]},
    ]


async def advance_window(db: AsyncDatabase, topic: str) -> dict:
    """Count one record into the window and return the window after it."""
    collection = db[ALERT_COLLECTION]
    pipeline = window_pipeline(topic)
    for attempt in (1, 2):
        try:
            return await collection.find_one_and_update(
                {"_id": ALERT_WINDOW_ID}, pipeline, upsert=True, return_document=ReturnDocument.AFTER
            )
        except DuplicateKeyError:
            if attempt == 2:
                raise
    return {}  # unreachable


def _api_path(tenant_id: Any, event_id: Optional[str] = None) -> str:
    path = f"GET /api/v1/tenants/{tenant_id}/dead-letters"
    return f"{path}/{event_id}" if event_id else path


def format_record(service: str, record: dict, *, via_sweep: bool = False, carried: int = 0) -> str:
    """One record's notice. No event content: a summary and the error type only."""
    summary = record.get("summary") or {}
    tenant_id = record.get("tenant_id") or "unknown"
    lines = [
        f"[{service}] Dead letter: {record.get('topic')}",
        f"tenant: {tenant_id}  event_id: {record.get('event_id') or record.get('_id')}",
    ]
    parts = []
    if summary.get("store_code") is not None:
        parts.append(f"store {summary['store_code']}")
    if summary.get("terminal_no") is not None:
        parts.append(f"terminal {summary['terminal_no']}")
    if summary.get("transaction_no") is not None:
        parts.append(f"transaction {summary['transaction_no']}")
    if summary.get("business_date") is not None:
        parts.append(f"business date {summary['business_date']}")
    if summary.get("business_counter") is not None:
        parts.append(f"counter {summary['business_counter']}")
    if parts:
        lines.append(" / ".join(parts))
    error_type = (record.get("last_error") or "unknown").split(":", 1)[0]
    lines.append(f"last error: {error_type}")
    if via_sweep:
        lines.append(
            f"retries ran out before the subscriber gave up ({record.get('failure_count', 0)} failures recorded); "
            f"the original is also in dlq-{service}-{record.get('topic')}"
        )
        lines.append(misconfigured_retries_hint())
    else:
        lines.append(f"gave up after {record.get('failure_count', 0)} failures")
    lines.append(_api_path(tenant_id, record.get("event_id") or record.get("_id")))
    if carried:
        lines.append(
            f"({carried} more dead letters in the previous 5 minutes were not notified one by one; "
            f"see {_api_path(tenant_id)})"
        )
    return "\n".join(lines)


def format_summary(service: str, tenant_id: Any, window: dict) -> str:
    topics = window.get("topics") or {}
    breakdown = ", ".join(f"{name} {count}" for name, count in sorted(topics.items()))
    return (
        f"[{service}] Dead letters are piling up for tenant {tenant_id}: {window.get('count')} in 5 minutes "
        f"({breakdown}). Further ones in this window are not notified one by one; see {_api_path(tenant_id)}"
    )


def misconfigured_retries_hint() -> str:
    """What a stranded record says about the sidecar's retries (#230).

    One stranded record is usually a subscriber that restarted between two
    deliveries. Many mean the sidecar delivers fewer times than the subscriber
    counts before giving up, so every failing event ends in dlq-* first.
    """
    give_up = give_up_after_failures()
    return (
        f"if this keeps happening, the pub/sub retries are too few for giving up after {give_up} failures: "
        f"the inbound retry policy of the subscription components needs maxRetries >= {give_up + 1}"
    )


async def send(text: str, service: str) -> bool:
    """Send to Slack within SLACK_TIMEOUT_SECONDS. Never raises."""
    from kugel_common.utils import slack_notifier

    try:
        return bool(
            await asyncio.wait_for(
                slack_notifier.send_warning_notification(message=text, service=service), SLACK_TIMEOUT_SECONDS
            )
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - a notification never fails its caller
        logger.warning(f"Dead-letter notification not sent ({type(e).__name__})")
        return False


async def notify_new_pending(db: AsyncDatabase, service: str, record: dict, *, via_sweep: bool = False) -> bool:
    """
    Tell the operators a record became pending, through the window.

    Returns True when the record counts as notified: sent one by one, covered by
    the summary that was sent, or past the summary (the next window's first
    notice mentions it). The caller then writes ``notified_at``; otherwise the
    sweep sends it again later. Never raises.
    """
    try:
        window = await advance_window(db, record.get("topic") or "unknown")
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Dead-letter alert window not updated ({type(e).__name__}); notifying one by one")
        return await send(format_record(service, record, via_sweep=via_sweep), service)
    count = window.get("count", 1)
    if count <= INDIVIDUAL_LIMIT:
        carried = window.get("carried_suppressed", 0) if count == 1 else 0
        return await send(format_record(service, record, via_sweep=via_sweep, carried=carried), service)
    if count == SUMMARY_AT:
        return await send(format_summary(service, record.get("tenant_id"), window), service)
    return True

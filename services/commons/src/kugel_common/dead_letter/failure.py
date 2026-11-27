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
Recording a subscriber's failure, and deciding whether to give up (R-4).

Called by a subscription route when its handler core reports a failure; never by
a replay. One pipeline ``find_one_and_update`` counts the failure and, on the
DEAD_LETTER_GIVE_UP_AFTER_FAILURES-th of an episode, makes the record pending.
The decision is read from the document as it was before, so concurrent failures
of one event give up once.
"""

import asyncio
from enum import Enum
from logging import getLogger
from typing import Any, Optional

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure

from kugel_common.dead_letter import alerts
from kugel_common.dead_letter.document import (
    COUNTING_STATES,
    RECORD_TIMEOUT_SECONDS,
    RECORDED_STATES,
    build_summary,
    describe_failure,
    failure_type,
    give_up_after_failures,
)
from kugel_common.dead_letter.repository import DeadLetterRepository
from kugel_common.dead_letter.unrecordable import notify_unrecordable

logger = getLogger(__name__)


class FailureDecision(str, Enum):
    GAVE_UP = "gave_up"  # the record became pending: acknowledge
    ALREADY_RECORDED = "already_recorded"  # pending or replaying already: acknowledge
    KEEP_RETRYING = "keep_retrying"  # ask for redelivery


class DeadLetterUnrecordable(Exception):
    """The failure could not be recorded; the caller asks for redelivery."""


def decide(before: Optional[dict], give_up_after: int) -> FailureDecision:
    """The same rule as the pipeline, read from the record before the update."""
    state = (before or {}).get("state") or "none"
    if state in RECORDED_STATES:
        return FailureDecision.ALREADY_RECORDED
    if state in COUNTING_STATES:
        episode = (before or {}).get("episode_failure_count") or 0
        if episode + 1 >= give_up_after:
            return FailureDecision.GAVE_UP
    return FailureDecision.KEEP_RETRYING


def is_database_unreachable(error: Any) -> bool:
    """True when the failure, or what it wraps, is the database being unreachable."""
    seen = set()
    current = error
    while isinstance(current, BaseException) and id(current) not in seen:
        if isinstance(current, ConnectionFailure):
            return True
        seen.add(id(current))
        current = getattr(current, "original_exception", None) or current.__cause__ or current.__context__
    return False


async def record_failure(
    *,
    db: AsyncDatabase,
    service: str,
    topic: str,
    message: dict,
    error: BaseException | str,
) -> FailureDecision:
    """
    Count a failure of ``message`` at this subscriber.

    Raises:
        DeadLetterUnrecordable: the record could not be written (announced
            through ``notify_unrecordable`` first). The caller asks for
            redelivery; past the retries the event is in ``dlq-*``.
    """
    data = message.get("data") if isinstance(message, dict) else None
    data = data if isinstance(data, dict) else {}
    event_id = data.get("event_id")
    tenant_id = data.get("tenant_id")

    if is_database_unreachable(error):
        # The record would fail the same way; do not stretch the delivery.
        await notify_unrecordable(
            service=service, topic=topic, tenant_id=tenant_id, event_id=event_id, reason=failure_type(error)
        )
        raise DeadLetterUnrecordable("the database is unreachable")

    give_up_after = give_up_after_failures()
    repo = DeadLetterRepository(db)
    try:
        before = await asyncio.wait_for(
            repo.record_failure(
                event_id=event_id,
                tenant_id=tenant_id,
                service=service,
                topic=topic,
                message=message,
                summary=build_summary(data),
                last_error=describe_failure(error),
                give_up_after=give_up_after,
            ),
            RECORD_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        await notify_unrecordable(
            service=service, topic=topic, tenant_id=tenant_id, event_id=event_id, reason=type(e).__name__
        )
        raise DeadLetterUnrecordable(type(e).__name__) from e

    decision = decide(before, give_up_after)
    logger.warning(
        f"Failure recorded. service={service} topic={topic} event_id={event_id} decision={decision.value} "
        f"error={failure_type(error)}"
    )
    if decision is FailureDecision.GAVE_UP:
        record = await repo.get(event_id, with_message=False) or {}
        if await alerts.notify_new_pending(db, service, record):
            try:
                await repo.set_notified(event_id)
            except Exception as e:  # noqa: BLE001 - the sweep notifies again
                logger.warning(f"notified_at not written for {event_id} ({type(e).__name__})")
    return decision

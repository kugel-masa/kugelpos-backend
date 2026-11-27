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
Replaying a pending record into its own subscriber (R-3, R-7).

The replay claims the record (a new ``replay_claim_id``), calls the handler core
in this service with the stored CloudEvent within REPLAY_TIMEOUT_SECONDS, and
writes the result on the condition that it still holds the claim. A failed
replay leaves the record pending, with the reason and count updated; it is not
notified, the operator is looking at the answer. The publisher is told only after
the result is written, outside the time limit.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from logging import getLogger
from typing import Optional

from pymongo.asynchronous.database import AsyncDatabase

from kugel_common.dead_letter.document import (
    REPLAY_TIMEOUT_SECONDS,
    STATE_DISCARDED,
    STATE_PENDING,
    STATE_REPLAYED,
    SYSTEM_USER,
    describe_failure,
)
from kugel_common.dead_letter.outcome import HandlerOutcome, OutcomeKind
from kugel_common.dead_letter.repository import DeadLetterRepository

logger = getLogger(__name__)

# The handler core: (CloudEvent, topic) -> outcome
HandlerCore = Callable[[dict, str], Awaitable[HandlerOutcome]]
# Told after a replay processed the event: (CloudEvent, topic) -> None
OnProcessed = Callable[[dict, str], Awaitable[None]]

LATE_RESULT = "the record is now held by another replay; this result was not written"

_background_tasks: set = set()


class ReplayConflict(Exception):
    """The record is not pending (or is being replayed under a live claim)."""


class ReplayNotFound(Exception):
    """No such record."""


@dataclass
class ReplayResult:
    id: str
    outcome: str  # replayed / discarded / failed / conflict / not_found
    error: Optional[str] = None


async def replay_one(
    *,
    db: AsyncDatabase,
    event_id: str,
    user: str,
    core: HandlerCore,
    on_processed: Optional[OnProcessed] = None,
    timeout: float = REPLAY_TIMEOUT_SECONDS,
) -> ReplayResult:
    """
    Raises:
        ReplayNotFound: no record with this id
        ReplayConflict: the record cannot be claimed
    """
    repo = DeadLetterRepository(db)
    claim_id = uuid.uuid4().hex
    record = await repo.claim_replay(event_id, claim_id)
    if record is None:
        if await repo.get(event_id, with_message=False) is None:
            raise ReplayNotFound(event_id)
        raise ReplayConflict(event_id)

    message = record.get("message") or {}
    topic = record.get("topic") or ""
    try:
        outcome = await asyncio.wait_for(core(message, topic), timeout)
    except asyncio.CancelledError:
        raise
    except TimeoutError as e:
        outcome = HandlerOutcome.failed(e)
    except Exception as e:  # noqa: BLE001 - a replay reports, it does not raise
        outcome = HandlerOutcome.failed(e)

    if outcome.handled:
        written = await repo.finish_replay(event_id, claim_id, state=STATE_REPLAYED, resolved_by=user)
        result = ReplayResult(event_id, "replayed", None if written else LATE_RESULT)
        if on_processed is not None:
            try:
                await on_processed(message, topic)
            except Exception as e:  # noqa: BLE001 - the event is stored; telling the publisher is best-effort
                logger.warning(f"Publisher not told after replay of {event_id} ({type(e).__name__})")
    elif outcome.kind is OutcomeKind.DROPPED:
        note = f"dropped by the handler: {outcome.reason}"
        written = await repo.finish_replay(
            event_id, claim_id, state=STATE_DISCARDED, resolved_by=SYSTEM_USER, resolution_note=note
        )
        result = ReplayResult(event_id, "discarded", outcome.reason if written else LATE_RESULT)
    else:
        reason = describe_failure(outcome.failure)
        written = await repo.finish_replay(event_id, claim_id, state=STATE_PENDING, last_error=reason)
        result = ReplayResult(event_id, "failed", reason if written else f"{reason}; {LATE_RESULT}")
    logger.info(f"Replay of {event_id} by {user}: {result.outcome}{'' if written else ' (late, not written)'}")
    return result


async def replay_many(
    *,
    db: AsyncDatabase,
    event_ids: Iterable[str],
    user: str,
    core: HandlerCore,
    on_processed: Optional[OnProcessed] = None,
) -> list[ReplayResult]:
    """One by one; a record that cannot be claimed or found is skipped."""
    results = []
    for event_id in event_ids:
        try:
            results.append(await replay_one(db=db, event_id=event_id, user=user, core=core, on_processed=on_processed))
        except ReplayNotFound:
            results.append(ReplayResult(event_id, "not_found"))
        except ReplayConflict:
            results.append(ReplayResult(event_id, "conflict"))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - the rest go on
            logger.warning(f"Replay of {event_id} failed ({type(e).__name__})")
            results.append(ReplayResult(event_id, "failed", type(e).__name__))
    return results


def start_bulk_replay(**kwargs) -> asyncio.Task:
    """``replay_many`` in the background: not bound to the request (R-7)."""

    async def run():
        results = await replay_many(**kwargs)
        outcomes: dict[str, int] = {}
        for result in results:
            outcomes[result.outcome] = outcomes.get(result.outcome, 0) + 1
        logger.info(f"Bulk replay by {kwargs.get('user')} done: {outcomes}")

    task = asyncio.create_task(run(), name="dead-letter-bulk-replay")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

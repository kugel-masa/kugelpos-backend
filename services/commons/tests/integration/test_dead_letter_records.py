# Copyright 2026 masa@kugel
"""The dead-letter records against a real MongoDB (#230).

The pipeline updates decide states and notifications; these tests run them for
real: every cell of the failure column of the state table, the give-up
threshold, concurrent failures of one event, content with "$" in it, the
replay claim, the sweep, and the alert window.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from kugel_common.dead_letter import alerts, failure, sweep
from kugel_common.dead_letter.document import (
    ALERT_COLLECTION,
    COLLECTION,
    STATE_DISCARDED,
    STATE_FAILING,
    STATE_PENDING,
    STATE_REPLAYED,
    STATE_REPLAYING,
)
from kugel_common.dead_letter.failure import FailureDecision, record_failure
from kugel_common.dead_letter.outcome import HandlerOutcome
from kugel_common.dead_letter.replay import ReplayConflict, replay_one
from kugel_common.dead_letter.repository import DeadLetterRepository
from kugel_common.dead_letter.unrecordable import reset_windows

pytestmark = pytest.mark.asyncio

GIVE_UP = 3


def event(event_id="e-1", tenant_id="T1", **data):
    return {
        "id": "cloud-1",
        "topic": "topic-tranlog",
        "data": {"event_id": event_id, "tenant_id": tenant_id, "store_code": "5001", "terminal_no": 1, **data},
    }


@pytest.fixture
def sent(monkeypatch):
    """Slack replaced: every text that would be sent."""
    texts = []

    async def fake_send(text, service):
        texts.append(text)
        return True

    monkeypatch.setattr(alerts, "send", fake_send)
    monkeypatch.setattr(failure, "give_up_after_failures", lambda: GIVE_UP)
    reset_windows()
    return texts


async def fail(db, message=None, error="RuntimeError: boom"):
    return await record_failure(db=db, service="report", topic="topic-tranlog", message=message or event(), error=error)


async def stored(db, event_id="e-1"):
    return await db[COLLECTION].find_one({"_id": event_id})


async def test_failures_count_until_the_record_gives_up(test_db, sent):
    assert await fail(test_db) is FailureDecision.KEEP_RETRYING
    doc = await stored(test_db)
    assert doc["state"] == STATE_FAILING
    assert doc["message"]["data"]["event_id"] == "e-1"  # kept from the first failure
    assert doc["purge_at"] is not None
    assert await fail(test_db) is FailureDecision.KEEP_RETRYING
    assert await fail(test_db) is FailureDecision.GAVE_UP
    doc = await stored(test_db)
    assert doc["state"] == STATE_PENDING
    assert doc["purge_at"] is None
    assert doc["failure_count"] == 3
    assert doc["dead_count"] == 1
    assert doc["last_dead_at"] is not None
    assert doc["notified_at"] is not None
    assert len(sent) == 1
    assert "e-1" in sent[0] and "RuntimeError" in sent[0] and "boom" not in sent[0]


async def test_a_pending_record_is_acknowledged_at_once_without_a_notice(test_db, sent):
    for _ in range(GIVE_UP):
        await fail(test_db)
    assert await fail(test_db, error="ValueError: again") is FailureDecision.ALREADY_RECORDED
    doc = await stored(test_db)
    assert doc["state"] == STATE_PENDING
    assert doc["failure_count"] == GIVE_UP + 1
    assert doc["dead_count"] == 1
    assert doc["last_error"] == "ValueError: again"
    assert len(sent) == 1


@pytest.mark.parametrize("resolved", [STATE_REPLAYED, STATE_DISCARDED])
async def test_a_resolved_record_counts_a_new_episode_and_is_not_purged_mid_count(test_db, sent, resolved):
    soon = datetime.now(timezone.utc) + timedelta(minutes=1)
    await test_db[COLLECTION].insert_one(
        {
            "_id": "e-1",
            "event_id": "e-1",
            "state": resolved,
            "episode_failure_count": 0,
            "failure_count": 5,
            "dead_count": 1,
            "purge_at": soon,
            "resolved_by": "alice",
            "message": {"old": True},
        }
    )
    assert await fail(test_db) is FailureDecision.KEEP_RETRYING
    doc = await stored(test_db)
    assert doc["state"] == resolved
    assert doc["episode_failure_count"] == 1
    assert doc["purge_at"].replace(tzinfo=timezone.utc) > soon + timedelta(hours=23)
    assert doc["message"]["data"]["event_id"] == "e-1"  # the new delivery's content
    await fail(test_db)
    assert await fail(test_db) is FailureDecision.GAVE_UP
    doc = await stored(test_db)
    assert doc["state"] == STATE_PENDING
    assert doc["dead_count"] == 2
    assert doc["resolved_by"] is None
    assert len(sent) == 1


async def test_concurrent_failures_give_up_once(test_db, sent):
    await fail(test_db)
    decisions = await asyncio.gather(*[fail(test_db) for _ in range(8)])
    assert decisions.count(FailureDecision.GAVE_UP) == 1
    doc = await stored(test_db)
    assert doc["failure_count"] == 9
    assert doc["dead_count"] == 1
    assert len(sent) == 1


async def test_concurrent_first_failures_make_one_record_without_any_index(test_db, sent):
    await asyncio.gather(*[fail(test_db) for _ in range(5)])
    assert await test_db[COLLECTION].count_documents({}) == 1
    assert (await stored(test_db))["failure_count"] == 5


async def test_content_with_dollar_values_and_keys_is_stored_as_given(test_db, sent):
    message = event(note="$12.00", nested={"$weird": "$$ROOT"})
    await fail(test_db, message=message, error="KeyError: $field")
    doc = await stored(test_db)
    assert doc["message"]["data"]["note"] == "$12.00"
    assert doc["message"]["data"]["nested"] == {"$weird": "$$ROOT"}
    assert doc["last_error"] == "KeyError: $field"


async def test_an_unreachable_database_is_announced_not_recorded(test_db, sent):
    from pymongo.errors import ServerSelectionTimeoutError

    with pytest.raises(failure.DeadLetterUnrecordable):
        await fail(test_db, error=ServerSelectionTimeoutError("down"))
    assert await stored(test_db) is None
    assert len(sent) == 1 and "could not be recorded" in sent[0]


async def give_up(db, event_id="e-1"):
    for _ in range(GIVE_UP):
        await fail(db, message=event(event_id))


async def test_a_replay_that_fails_stays_pending(test_db, sent):
    await give_up(test_db)

    async def core(message, topic):
        return HandlerOutcome.failed(RuntimeError("still broken"))

    result = await replay_one(db=test_db, event_id="e-1", user="alice", core=core)
    assert result.outcome == "failed"
    doc = await stored(test_db)
    assert doc["state"] == STATE_PENDING
    assert doc["failure_count"] == GIVE_UP + 1
    # A foreign exception is described by its type only (#318)
    assert doc["last_error"] == "RuntimeError"


async def test_a_replay_that_works_resolves_the_record_and_tells_the_publisher(test_db, sent):
    await give_up(test_db)
    told = []

    async def core(message, topic):
        assert message["data"]["event_id"] == "e-1" and topic == "topic-tranlog"
        return HandlerOutcome.processed()

    async def on_processed(message, topic):
        told.append(message["data"]["event_id"])

    result = await replay_one(db=test_db, event_id="e-1", user="alice", core=core, on_processed=on_processed)
    assert (result.outcome, result.error) == ("replayed", None)
    doc = await stored(test_db)
    assert doc["state"] == STATE_REPLAYED and doc["resolved_by"] == "alice"
    assert doc["episode_failure_count"] == 0 and doc["purge_at"] is not None
    assert told == ["e-1"]


async def test_a_dropped_replay_discards_the_record(test_db, sent):
    await give_up(test_db)

    async def core(message, topic):
        return HandlerOutcome.dropped("schema: ['sales']")

    result = await replay_one(db=test_db, event_id="e-1", user="alice", core=core)
    assert result.outcome == "discarded"
    doc = await stored(test_db)
    assert doc["state"] == STATE_DISCARDED and doc["resolved_by"] == "system"
    assert doc["resolution_note"] == "dropped by the handler: schema: ['sales']"


async def test_concurrent_replays_process_once(test_db, sent):
    await give_up(test_db)
    calls = []

    async def core(message, topic):
        calls.append(1)
        await asyncio.sleep(0.2)
        return HandlerOutcome.processed()

    results = await asyncio.gather(
        replay_one(db=test_db, event_id="e-1", user="a", core=core),
        replay_one(db=test_db, event_id="e-1", user="b", core=core),
        return_exceptions=True,
    )
    assert len(calls) == 1
    assert sum(isinstance(r, ReplayConflict) for r in results) == 1


async def test_a_late_replay_does_not_overwrite_the_new_claim(test_db, sent):
    await give_up(test_db)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(message, topic):
        started.set()
        await release.wait()
        return HandlerOutcome.processed()

    first = asyncio.create_task(replay_one(db=test_db, event_id="e-1", user="a", core=slow))
    await started.wait()
    # The first claim's lease ran out
    await test_db[COLLECTION].update_one(
        {"_id": "e-1"}, {"$set": {"replay_claimed_at": datetime.now(timezone.utc) - timedelta(minutes=11)}}
    )

    async def failing(message, topic):
        return HandlerOutcome.failed("RuntimeError")

    second = await replay_one(db=test_db, event_id="e-1", user="b", core=failing)
    assert second.outcome == "failed"
    release.set()
    late = await first
    assert late.outcome == "replayed" and "not written" in late.error
    assert (await stored(test_db))["state"] == STATE_PENDING


async def test_a_failure_during_a_replay_is_acknowledged_and_leaves_the_state(test_db, sent):
    await give_up(test_db)
    repo = DeadLetterRepository(test_db)
    assert await repo.claim_replay("e-1", "claim-1") is not None
    assert await fail(test_db) is FailureDecision.ALREADY_RECORDED
    assert (await stored(test_db))["state"] == STATE_REPLAYING


async def test_discard_only_from_pending(test_db, sent):
    await fail(test_db)
    repo = DeadLetterRepository(test_db)
    assert await repo.discard("e-1", "alice", "test data") is None
    await fail(test_db)
    await fail(test_db)
    doc = await repo.discard("e-1", "alice", "test data")
    assert doc["state"] == STATE_DISCARDED and doc["resolution_note"] == "test data"


async def test_the_sweep_resolves_stranded_failing_records(test_db, sent, monkeypatch):
    for event_id in ("done", "stranded", "recent"):
        await fail(test_db, message=event(event_id))
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    await test_db[COLLECTION].update_many({"_id": {"$in": ["done", "stranded"]}}, {"$set": {"last_failed_at": old}})

    async def is_processed(event_id):
        return event_id == "done"

    sweeper = sweep.DeadLetterSweeper(service="report", db_name_prefix="x", is_processed=is_processed)
    counts = await sweeper.sweep_tenant(test_db)
    assert counts["deleted"] == 1 and counts["promoted"] == 1
    assert await stored(test_db, "done") is None
    stranded = await stored(test_db, "stranded")
    assert stranded["state"] == STATE_PENDING and stranded["notified_at"] is not None
    assert (await stored(test_db, "recent"))["state"] == STATE_FAILING
    assert any("retries ran out" in text for text in sent)
    # A second sweep finds nothing to do
    assert await sweeper.sweep_tenant(test_db) == {"deleted": 0, "promoted": 0, "renotified": 0}


async def test_the_sweep_sends_notifications_that_were_missed(test_db, sent, monkeypatch):
    async def not_sent(text, service):
        return False

    monkeypatch.setattr(alerts, "send", not_sent)
    await give_up(test_db)
    assert (await stored(test_db))["notified_at"] is None
    await test_db[COLLECTION].update_one(
        {"_id": "e-1"}, {"$set": {"last_dead_at": datetime.now(timezone.utc) - timedelta(minutes=5)}}
    )
    resent = []

    async def ok(text, service):
        resent.append(text)
        return True

    monkeypatch.setattr(alerts, "send", ok)
    sweeper = sweep.DeadLetterSweeper(service="report", db_name_prefix="x", is_processed=None)
    counts = await sweeper.sweep_tenant(test_db)
    assert counts["renotified"] == 1 and len(resent) == 1
    doc = await stored(test_db)
    assert doc["notified_at"] is not None and doc["notify_attempts"] == 1
    assert (await sweeper.sweep_tenant(test_db))["renotified"] == 0


async def test_the_alert_window_counts_concurrent_records_once_each(test_db):
    windows = await asyncio.gather(*[alerts.advance_window(test_db, "topic-tranlog") for _ in range(12)])
    counts = sorted(w["count"] for w in windows)
    assert counts == list(range(1, 13))
    final = await test_db[ALERT_COLLECTION].find_one({})
    assert final["topics"] == {"topic-tranlog": 12}
    assert final["suppressed"] == 2


async def test_a_new_window_carries_what_the_last_one_held_back(test_db):
    for _ in range(12):
        await alerts.advance_window(test_db, "topic-cashlog")
    await test_db[ALERT_COLLECTION].update_one(
        {}, {"$set": {"window_started_at": datetime.now(timezone.utc) - timedelta(minutes=6)}}
    )
    window = await alerts.advance_window(test_db, "topic-tranlog")
    assert window["count"] == 1 and window["carried_suppressed"] == 2 and window["suppressed"] == 0
    assert window["topics"] == {"topic-tranlog": 1}


async def test_the_ttl_and_list_indexes_are_created(test_db, db_helper):
    from kugel_common.dead_letter.repository import create_dead_letter_collections_async

    await create_dead_letter_collections_async(test_db.name)
    info = await test_db[COLLECTION].index_information()
    ttl = [i for i in info.values() if i.get("expireAfterSeconds") == 0]
    assert ttl and ttl[0]["key"] == [("purge_at", 1)]
    assert any(i["key"] == [("state", 1), ("last_dead_at", -1)] for i in info.values())
    assert ALERT_COLLECTION in await test_db.list_collection_names()

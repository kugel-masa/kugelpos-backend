# Copyright 2026 masa@kugel
"""Unit tests of the dead-letter pieces that need no database (#230)."""

import pytest
from pydantic import BaseModel, ValidationError
from pymongo.errors import AutoReconnect, ServerSelectionTimeoutError

from kugel_common.dead_letter import alerts, unrecordable
from kugel_common.dead_letter.document import (
    LAST_ERROR_MAX_LENGTH,
    DeadLetterDocument,
    build_summary,
    describe_failure,
    failure_type,
    give_up_after_failures,
)
from kugel_common.dead_letter.failure import FailureDecision, decide, is_database_unreachable
from kugel_common.dead_letter.outcome import HandlerOutcome, OutcomeKind
from kugel_common.dead_letter.repository import DEAD_LETTER_INDEXES, failure_pipeline
from kugel_common.exceptions import RepositoryException


def test_a_subscriber_gives_up_on_the_17th_failure_by_default():
    assert give_up_after_failures() == 17


def test_a_record_is_read_back_with_its_id_as_the_event_id():
    doc = DeadLetterDocument.from_mongo({"_id": "e-1", "state": "pending", "failure_count": 3})
    assert doc.event_id == "e-1" and doc.state == "pending" and doc.failure_count == 3


def test_the_summary_carries_identifiers_and_never_content():
    data = {"store_code": "5001", "terminal_no": 1, "business_counter": 7, "sales": {"total": 100}, "api_key": "k"}
    assert build_summary(data) == {"store_code": "5001", "terminal_no": 1, "business_counter": 7}
    assert build_summary("not a dict") == {}


def test_a_failure_is_described_without_the_values_it_echoes():
    class Model(BaseModel):
        amount: int

    with pytest.raises(ValidationError) as caught:
        Model(amount="secret-value")
    assert "secret-value" not in describe_failure(caught.value)
    assert describe_failure(RuntimeError("customer 0123 failed")) == "RuntimeError"
    assert describe_failure("ValueError: x") == "ValueError: x"
    assert len(describe_failure("x" * 1000)) == LAST_ERROR_MAX_LENGTH


def test_a_notification_carries_the_failure_type_only():
    assert failure_type(RuntimeError("secret")) == "RuntimeError"
    assert failure_type("KeyError: secret") == "KeyError"


def test_handler_outcomes():
    assert HandlerOutcome.processed().handled
    assert HandlerOutcome.already_processed().handled
    dropped = HandlerOutcome.dropped("schema")
    assert dropped.kind is OutcomeKind.DROPPED and not dropped.handled
    error = RuntimeError("x")
    failed = HandlerOutcome.failed(error)
    assert failed.kind is OutcomeKind.FAILED and failed.failure is error and failed.reason == "RuntimeError"
    assert HandlerOutcome.failed("timeout").failure == "timeout"


@pytest.mark.parametrize(
    "before, decision",
    [
        (None, FailureDecision.KEEP_RETRYING),
        ({"state": "failing", "episode_failure_count": 15}, FailureDecision.KEEP_RETRYING),
        ({"state": "failing", "episode_failure_count": 16}, FailureDecision.GAVE_UP),
        ({"state": "pending", "episode_failure_count": 17}, FailureDecision.ALREADY_RECORDED),
        ({"state": "replaying", "episode_failure_count": 0}, FailureDecision.ALREADY_RECORDED),
        ({"state": "replayed", "episode_failure_count": 0}, FailureDecision.KEEP_RETRYING),
        ({"state": "replayed", "episode_failure_count": 16}, FailureDecision.GAVE_UP),
        ({"state": "discarded", "episode_failure_count": 16}, FailureDecision.GAVE_UP),
    ],
)
def test_the_decision_follows_the_state_table(before, decision):
    assert decide(before, 17) is decision


def test_a_new_record_gives_up_at_once_only_when_the_threshold_is_one():
    assert decide(None, 1) is FailureDecision.GAVE_UP


def test_an_unreachable_database_is_seen_through_wrappers():
    assert is_database_unreachable(ServerSelectionTimeoutError("x"))
    assert is_database_unreachable(AutoReconnect("x"))
    wrapped = RepositoryException("save failed", "log_tran", None, AutoReconnect("x"))
    assert is_database_unreachable(wrapped)
    try:
        try:
            raise AutoReconnect("x")
        except AutoReconnect as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as outer:
        assert is_database_unreachable(outer)
    assert not is_database_unreachable(RuntimeError("x"))
    assert not is_database_unreachable("ServerSelectionTimeoutError")


def test_external_values_go_into_the_pipeline_as_literals():
    pipeline = failure_pipeline(
        event_id="$e",
        tenant_id="$t",
        service="report",
        topic="topic-tranlog",
        message={"$k": "$v"},
        summary={},
        last_error="$err",
        give_up_after=17,
    )
    fields = pipeline[3]["$set"]
    assert fields["event_id"] == {"$literal": "$e"}
    assert fields["last_error"] == {"$literal": "$err"}
    assert {"$literal": {"$k": "$v"}} in fields["message"]["$cond"]


def test_the_indexes_serve_the_list_the_sweep_and_the_ttl():
    keys = [list(i["keys"].items()) for i in DEAD_LETTER_INDEXES]
    assert [("state", 1), ("last_dead_at", -1)] in keys
    assert [("topic", 1), ("state", 1), ("last_dead_at", -1)] in keys
    assert [("state", 1), ("last_failed_at", 1)] in keys
    assert [("state", 1), ("notified_at", 1), ("last_dead_at", 1)] in keys
    ttl = [i for i in DEAD_LETTER_INDEXES if "expireAfterSeconds" in i]
    assert ttl == [{"keys": {"purge_at": 1}, "unique": False, "expireAfterSeconds": 0}]


def test_a_record_notice_has_no_content_and_points_at_the_api():
    record = {
        "_id": "e-1",
        "event_id": "e-1",
        "tenant_id": "T1",
        "topic": "topic-opencloselog",
        "summary": {"store_code": "5001", "terminal_no": 1, "business_date": "20261124", "business_counter": 7},
        "last_error": "RuntimeError: settlement 9f could not be finalized",
        "failure_count": 17,
        "message": {"data": {"api_key": "secret"}},
    }
    text = alerts.format_record("report", record)
    assert "store 5001 / terminal 1 / business date 20261124 / counter 7" in text
    assert "last error: RuntimeError" in text and "settlement" not in text
    assert "secret" not in text
    assert "gave up after 17 failures" in text
    assert "GET /api/v1/tenants/T1/dead-letters/e-1" in text
    swept = alerts.format_record("report", record, via_sweep=True, carried=4)
    assert "retries ran out" in swept and "dlq-report-topic-opencloselog" in swept
    assert "4 more dead letters" in swept
    # A stranded record points at the sidecar's retries; a give-up does not
    assert "maxRetries >= 18" in swept
    assert "maxRetries" not in text


def test_the_retries_hint_follows_the_give_up_setting(monkeypatch):
    monkeypatch.setattr(alerts, "give_up_after_failures", lambda: 2)
    assert "giving up after 2 failures" in alerts.misconfigured_retries_hint()
    assert "maxRetries >= 3" in alerts.misconfigured_retries_hint()


@pytest.mark.parametrize("webhook, warned", [("", True), ("https://hooks.example.invalid/x", False)])
def test_the_sweep_warns_at_startup_when_nobody_is_notified(monkeypatch, caplog, webhook, warned):
    from kugel_common.dead_letter import sweep
    from kugel_common.utils import slack_notifier

    monkeypatch.setattr(slack_notifier, "SLACK_WEBHOOK_URL", webhook)
    sweeper = sweep.DeadLetterSweeper(service="report", db_name_prefix="db_report", is_processed=None)
    with caplog.at_level("WARNING", logger="kugel_common.dead_letter.sweep"):
        sweeper._warn_if_nobody_is_notified()
    assert ("SLACK_WEBHOOK_URL is not set" in caplog.text) is warned


def test_the_summary_notice_lists_counts_per_topic():
    text = alerts.format_summary("report", "T1", {"count": 10, "topics": {"topic-tranlog": 9, "topic-cashlog": 1}})
    assert "10 in 5 minutes" in text and "topic-cashlog 1, topic-tranlog 9" in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "count, sends, counted",
    [(1, 1, True), (9, 1, True), (10, 1, True), (11, 0, True)],
)
async def test_the_window_decides_what_is_sent(monkeypatch, count, sends, counted):
    texts = []

    async def fake_window(db, topic):
        return {"count": count, "topics": {topic: count}, "carried_suppressed": 0}

    async def fake_send(text, service):
        texts.append(text)
        return True

    monkeypatch.setattr(alerts, "advance_window", fake_window)
    monkeypatch.setattr(alerts, "send", fake_send)
    record = {"event_id": "e-1", "tenant_id": "T1", "topic": "topic-tranlog", "failure_count": 17}
    assert await alerts.notify_new_pending(None, "report", record) is counted
    assert len(texts) == sends
    if count == 10:
        assert "piling up" in texts[0]


@pytest.mark.asyncio
async def test_a_failed_send_leaves_the_record_unnotified(monkeypatch):
    async def fake_window(db, topic):
        return {"count": 1}

    async def fake_send(text, service):
        return False

    monkeypatch.setattr(alerts, "advance_window", fake_window)
    monkeypatch.setattr(alerts, "send", fake_send)
    assert await alerts.notify_new_pending(None, "report", {"topic": "topic-tranlog"}) is False


@pytest.mark.asyncio
async def test_send_never_raises_and_gives_up_after_its_time(monkeypatch):
    import asyncio

    from kugel_common.utils import slack_notifier

    async def hangs(**kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(slack_notifier, "send_warning_notification", hangs)
    monkeypatch.setattr(alerts, "SLACK_TIMEOUT_SECONDS", 0.05)
    assert await alerts.send("x", "report") is False

    async def raises(**kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(slack_notifier, "send_warning_notification", raises)
    assert await alerts.send("x", "report") is False


@pytest.mark.asyncio
async def test_unrecordable_events_are_announced_once_per_window(monkeypatch):
    texts = []
    clock = [1000.0]

    async def fake_send(text, service):
        texts.append(text)
        return True

    monkeypatch.setattr(alerts, "send", fake_send)
    monkeypatch.setattr(unrecordable.time, "monotonic", lambda: clock[0])
    unrecordable.reset_windows()
    for _ in range(4):
        await unrecordable.notify_unrecordable(
            service="report",
            topic="topic-tranlog",
            tenant_id=None,
            event_id="e-1",
            reason="ServerSelectionTimeoutError",
        )
    assert len(texts) == 1
    assert "tenant: unknown" in texts[0] and "dlq-report-topic-tranlog" in texts[0]
    clock[0] += 301
    await unrecordable.notify_unrecordable(
        service="report", topic="topic-tranlog", tenant_id="T1", event_id="e-2", reason="AutoReconnect"
    )
    assert len(texts) == 2 and "(3 more in the previous 5 minutes)" in texts[1]


@pytest.mark.asyncio
async def test_an_unrecordable_notice_never_raises(monkeypatch):
    async def boom(text, service):
        raise RuntimeError("x")

    monkeypatch.setattr(alerts, "send", boom)
    unrecordable.reset_windows()
    await unrecordable.notify_unrecordable(service="s", topic=None, tenant_id=None, event_id=None, reason="r")

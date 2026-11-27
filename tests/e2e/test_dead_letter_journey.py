# Copyright 2026 masa@kugel
"""Dead letters end to end (#230), on the stack with docker-compose.e2e-deadletter.yaml.

The overlay makes report, journal and stock give up on the 2nd failure, has
their sidecars deliver 4 times 2 seconds apart, runs the sweep every 5 seconds
(stranded after 20), and sends Slack notifications to a local sink that these
tests read. Without the overlay every test here skips.

Faults are MongoDB collection validators that the tests add and remove: a
validator nothing passes makes every insert into that collection fail, as a
handler bug or a broken database would, and taking it off is the fix.

1. A sale both report and journal fail on: one record and one notice per
   subscriber within a minute, nothing in dlq-*, stock unaffected; after the
   fix, a single replay (report) and a bulk replay (journal) store it.
2. A close log whose settlement cannot be made final (#343): the daily report is
   refused until the replay makes it final.
3. A failure that cannot be recorded: one "could not be recorded" notice, the
   event in dlq-*, and once moved back with a shovel (R-13) it is recorded.
4. Deliveries the subscriber does not count: the sweep promotes the stranded
   record and says the retries ran out.
"""
import json
import os
import shutil
import subprocess
import time

import httpx
import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from .test_pos_full_journey import _client, _new_tenant_id
from .test_settlement_journey import _report, _sell, _setup

SINK = os.environ.get("DEAD_LETTER_SLACK_SINK", "http://localhost:8099")
RABBITMQ = os.environ.get("RABBITMQ_CONTAINER", "rabbitmq")
NOTHING_PASSES = {"_dead_letter_e2e_fault": {"$exists": True}}


def _overlay_is_up() -> bool:
    try:
        return httpx.get(f"{SINK}/messages", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _overlay_is_up() or shutil.which("docker") is None,
    reason="needs the stack started with services/docker-compose.e2e-deadletter.yaml",
)


# -- helpers --------------------------------------------------------------------


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)


def _queue_length(queue: str) -> int:
    out = _docker("exec", RABBITMQ, "rabbitmqctl", "-q", "list_queues", "name", "messages").stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == queue:
            return int(parts[1])
    return 0


def _purge(queue: str) -> None:
    _docker("exec", RABBITMQ, "rabbitmqctl", "-q", "purge_queue", queue)


def _messages() -> list[str]:
    return httpx.get(f"{SINK}/messages", timeout=5.0).json()


def _about(tenant_id: str) -> list[str]:
    return [m for m in _messages() if tenant_id in m]


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true"))
    yield client
    client.close()


@pytest.fixture
def fault(mongo):
    """Make a collection refuse writes; every fault is taken off at the end."""
    applied: list[tuple[str, str]] = []

    def apply(db_name: str, collection: str, validator: dict = NOTHING_PASSES) -> None:
        db = mongo[db_name]
        try:
            db.command("collMod", collection, validator=validator, validationLevel="strict", validationAction="error")
        except OperationFailure:
            db.create_collection(collection, validator=validator, validationLevel="strict", validationAction="error")
        applied.append((db_name, collection))

    def remove(db_name: str, collection: str) -> None:
        mongo[db_name].command("collMod", collection, validator={}, validationLevel="off")
        applied.remove((db_name, collection))

    apply.remove = remove
    yield apply
    for db_name, collection in list(applied):
        remove(db_name, collection)


def _dead_letters(url_env: str, headers: dict, tenant_id: str, **params) -> list[dict]:
    with _client(url_env) as c:
        resp = c.get(f"/api/v1/tenants/{tenant_id}/dead-letters", headers=headers, params={"state": "all", **params})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _one(url_env, headers, tenant_id, topic, state=None):
    """The tenant's one record on this topic (optionally in this state), else None."""
    rows = [r for r in _dead_letters(url_env, headers, tenant_id, topic=topic) if state is None or r["state"] == state]
    return rows[0] if len(rows) == 1 else None


def _open_terminal(tenant_id: str):
    headers, terminal_id, api_key = _setup(tenant_id)
    key = {"X-API-KEY": api_key}
    with _client("URL_TERMINAL") as c:
        assert c.post(f"/api/v1/terminals/{terminal_id}/sign-in", json={"staff_id": "S001"}, headers=key).status_code == 200
        assert c.post(f"/api/v1/terminals/{terminal_id}/open", json={"initial_amount": 1000.0}, headers=key).status_code == 200
    return headers, terminal_id, api_key


# -- 1. a sale two subscribers fail on --------------------------------------------


def test_a_sale_two_subscribers_fail_on_is_recorded_and_notified_once_each_and_replayed(wait_for, fault):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _open_terminal(tenant_id)
    dlq = {q: _queue_length(q) for q in ("dlq-report-topic-tranlog", "dlq-journal-topic-tranlog")}
    fault(f"db_report_{tenant_id}", "log_tran")
    fault(f"db_journal_{tenant_id}", "log_tran")

    sold_at = time.monotonic()
    _sell(tenant_id, terminal_id, api_key)

    report = wait_for(lambda: _one("URL_REPORT", headers, tenant_id, "topic-tranlog", "pending"),
                      timeout=60.0, description="report's dead letter")
    journal = wait_for(lambda: _one("URL_JOURNAL", headers, tenant_id, "topic-tranlog", "pending"),
                       timeout=60.0, description="journal's dead letter")
    assert time.monotonic() - sold_at < 60  # SC-001
    assert report["eventId"] == journal["eventId"]
    assert report["service"] == "report" and journal["service"] == "journal"
    wait_for(lambda: len(_about(tenant_id)) >= 2, timeout=15.0, description="the notices")
    notices = _about(tenant_id)
    assert sum("[report] Dead letter: topic-tranlog" in m for m in notices) == 1, notices
    assert sum("[journal] Dead letter: topic-tranlog" in m for m in notices) == 1, notices
    assert all("gave up after 2 failures" in m for m in notices)
    # Recorded and acknowledged: nothing went to the queue of last resort
    assert {q: _queue_length(q) for q in dlq} == dlq
    # Stock took the sale; it has nothing to record
    assert _dead_letters("URL_STOCK", headers, tenant_id) == []

    fault.remove(f"db_report_{tenant_id}", "log_tran")
    fault.remove(f"db_journal_{tenant_id}", "log_tran")

    with _client("URL_REPORT") as c:
        one = c.post(f"/api/v1/tenants/{tenant_id}/dead-letters/{report['id']}/replay", headers=headers)
    assert one.status_code == 200, one.text
    assert one.json()["data"]["outcome"] == "replayed"
    flash = _report(headers, tenant_id, "flash", terminal_no=1)
    assert flash.json()["data"]["salesGross"]["count"] == 1

    with _client("URL_JOURNAL") as c:
        bulk = c.post(f"/api/v1/tenants/{tenant_id}/dead-letters/replay", headers=headers, json={"ids": [journal["id"]]})
    assert bulk.status_code == 202, bulk.text
    assert bulk.json()["data"]["accepted"] == [journal["id"]]
    wait_for(lambda: _one("URL_JOURNAL", headers, tenant_id, "topic-tranlog", "replayed"),
             timeout=20.0, description="the bulk replay's result in the list")
    with _client("URL_JOURNAL") as c:
        journals = c.get(f"/api/v1/tenants/{tenant_id}/stores/5343/journals", headers=headers)
    assert journals.status_code == 200, journals.text
    assert any(j.get("transactionNo") == report["summary"]["transactionNo"] for j in journals.json()["data"]), journals.text
    # Replaying told nobody new: still one notice each
    assert len(_about(tenant_id)) == 2


# -- 2. a close log whose settlement cannot be made final (#343) -------------------


def test_a_close_log_that_cannot_finalize_is_replayed_and_the_daily_report_answers(wait_for, fault):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _open_terminal(tenant_id)
    key = {"X-API-KEY": api_key}
    takings = _sell(tenant_id, terminal_id, api_key)
    wait_for(lambda: (_report(headers, tenant_id, "flash", terminal_no=1).json().get("data") or {})
             .get("salesGross", {}).get("count") == 1, timeout=20.0, description="the sale in report")
    # A provisional record can be written; making it final cannot
    fault(f"db_report_{tenant_id}", "settlement_record", {"state": {"$ne": "final"}})

    with _client("URL_TERMINAL") as c:
        closed = c.post(f"/api/v1/terminals/{terminal_id}/close", json={"physicalAmount": 1000.0 + takings}, headers=key)
    assert closed.status_code == 200, closed.text

    record = wait_for(lambda: _one("URL_REPORT", headers, tenant_id, "topic-opencloselog", "pending"),
                      timeout=60.0, description="the close log's dead letter")
    daily = _report(headers, tenant_id, "daily", terminal_no=1)
    assert daily.status_code != 200 and daily.json()["userError"]["code"] == "412101", daily.text
    wait_for(lambda: any("Dead letter: topic-opencloselog" in m for m in _about(tenant_id)),
             timeout=15.0, description="the close log's notice")

    fault.remove(f"db_report_{tenant_id}", "settlement_record")
    with _client("URL_REPORT") as c:
        replayed = c.post(f"/api/v1/tenants/{tenant_id}/dead-letters/{record['id']}/replay", headers=headers)
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["outcome"] == "replayed"

    with _client("URL_REPORT") as c:
        rows = c.get(f"/api/v1/tenants/{tenant_id}/stores/5343/settlements", headers=headers,
                     params={"terminal_no": 1}).json()["data"]
    assert rows and rows[0]["state"] == "final"
    daily = _report(headers, tenant_id, "daily", terminal_no=1)
    assert daily.status_code == 200, daily.text
    assert daily.json()["data"]["salesGross"]["count"] == 1


# -- 3. a failure that cannot be recorded ------------------------------------------


def test_an_unrecordable_failure_is_announced_kept_in_the_dlq_and_recorded_after_a_shovel(wait_for, fault):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _open_terminal(tenant_id)
    queue, dlq = "report-topic-tranlog", "dlq-report-topic-tranlog"
    _purge(dlq)
    fault(f"db_report_{tenant_id}", "log_tran")
    fault(f"db_report_{tenant_id}", "dead_letter")

    _sell(tenant_id, terminal_id, api_key)

    wait_for(lambda: _queue_length(dlq) == 1, timeout=60.0, description="the event in the dlq")
    notices = [m for m in _about(tenant_id) if "could not be recorded" in m]
    # One per service process every 5 minutes: a run within 5 minutes of the
    # last one in the same process is carried into a later notice instead.
    assert len(notices) <= 1, notices
    if notices:
        assert "[report] Events could not be recorded as dead letters: topic-tranlog" in notices[0]
        assert dlq in notices[0]

    # The recording works again; the cause of the failure is still there
    fault.remove(f"db_report_{tenant_id}", "dead_letter")
    enabled = _docker("exec", RABBITMQ, "rabbitmq-plugins", "enable", "--quiet", "rabbitmq_shovel")
    assert enabled.returncode == 0, enabled.stderr
    shovel = json.dumps({
        "src-protocol": "amqp091", "src-uri": "amqp://", "src-queue": dlq, "src-delete-after": "queue-length",
        "dest-protocol": "amqp091", "dest-uri": "amqp://", "dest-queue": queue,
    })
    moved = _docker("exec", RABBITMQ, "rabbitmqctl", "set_parameter", "shovel", f"requeue-{queue}", shovel)
    assert moved.returncode == 0, moved.stderr

    record = wait_for(lambda: _one("URL_REPORT", headers, tenant_id, "topic-tranlog", "pending"),
                      timeout=60.0, description="the shovelled event recorded")
    assert _queue_length(dlq) == 0

    fault.remove(f"db_report_{tenant_id}", "log_tran")
    with _client("URL_REPORT") as c:
        replayed = c.post(f"/api/v1/tenants/{tenant_id}/dead-letters/{record['id']}/replay", headers=headers)
    assert replayed.json()["data"]["outcome"] == "replayed", replayed.text


# -- 4. deliveries the subscriber misses -------------------------------------------


def test_the_sweep_promotes_a_record_whose_deliveries_ran_out(wait_for, fault):
    """The first failure is counted, the rest are not, and the deliveries run out.

    Pausing report does not do it: its sidecar shares report's network
    namespace, so a delivery to the paused app hangs instead of failing. The
    record store refusing writes after the first count leaves the record
    stranded at one failure just the same, which is what a subscriber that
    restarts between deliveries leaves behind.
    """
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _open_terminal(tenant_id)
    dlq = "dlq-report-topic-tranlog"
    _purge(dlq)
    fault(f"db_report_{tenant_id}", "log_tran")

    _sell(tenant_id, terminal_id, api_key)
    wait_for(lambda: _first_failure_seen(tenant_id), timeout=30.0, interval=0.1,
             description="the first failure recorded")
    fault(f"db_report_{tenant_id}", "dead_letter")
    wait_for(lambda: _queue_length(dlq) == 1, timeout=60.0, description="the deliveries running out")
    fault.remove(f"db_report_{tenant_id}", "dead_letter")

    record = wait_for(lambda: _one("URL_REPORT", headers, tenant_id, "topic-tranlog", "pending"),
                      timeout=60.0, description="the sweep promoting the stranded record")
    assert record["failureCount"] == 1
    notice = wait_for(lambda: [m for m in _about(tenant_id) if "retries ran out" in m], timeout=20.0,
                      description="the sweep's notice")
    assert dlq in notice[0]
    _purge(dlq)


def _first_failure_seen(tenant_id: str) -> bool:
    client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?replicaSet=rs0&directConnection=true"))
    try:
        doc = client[f"db_report_{tenant_id}"]["dead_letter"].find_one({"state": "failing"})
        return bool(doc)
    finally:
        client.close()


@pytest.fixture(autouse=True)
def _remove_the_shovel():
    yield
    _docker("exec", RABBITMQ, "rabbitmqctl", "-q", "clear_parameter", "shovel", "requeue-report-topic-tranlog")

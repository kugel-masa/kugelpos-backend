# Copyright 2026 masa@kugel
"""Settlement e2e on the carried path (#343, R-13), and with report away (R-7).

1. The terminal carries the signed snapshot and numbers its transactions
   1..N in the session (seq / receiptCounter). Number 3 never reaches cart, and
   the close declares seq=5: the settlement must name 3 and 5 as missing, the
   close answer and the daily report must say so, and the daily report must say
   which terminal is missing them.
2. Report cannot answer: the close is refused with 503 / 406016, the terminal
   stays open, and once report is back the same close goes through.
"""
import json
import shutil
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
import os

import pytest

from .test_pos_full_journey import _client, _new_tenant_id
from .test_settlement_journey import ITEM, STORE, _report, _setup

FLOAT = 5000.0
REPORT_CONTAINER = os.environ.get("REPORT_CONTAINER", "services-report-1")


def _open(terminal_id, api_key):
    key = {"X-API-KEY": api_key}
    with _client("URL_TERMINAL") as c:
        assert c.post(f"/api/v1/terminals/{terminal_id}/sign-in", json={"staff_id": "S001"}, headers=key).status_code == 200
        assert c.post(f"/api/v1/terminals/{terminal_id}/open", json={"initial_amount": FLOAT}, headers=key).status_code == 200


def _carried_sale(terminal_id, api_key, number):
    """One cash sale on the carried path, numbered `number` by the terminal; returns its total."""
    key = {"X-API-KEY": api_key}
    q = f"?terminal_id={terminal_id}"
    now = datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))).strftime("%Y-%m-%dT%H:%M:%S")
    with _client("URL_CART") as c:
        r = c.post(f"/api/v1/carts{q}", headers=key, json={
            "carrySnapshot": True, "transaction_type": 101, "user_id": "S001", "user_name": "Staff",
        })
        assert r.status_code == 201, r.text
        cart_id, snapshot = r.json()["data"]["cartId"], r.json()["data"]["signedSnapshot"]

        def step(path, payload):
            resp = c.post(f"/api/v1/carts/{cart_id}/{path}{q}", headers=key, json={"signedSnapshot": snapshot, "payload": payload})
            assert resp.status_code == 200, resp.text
            return resp.json()["data"]

        snapshot = step("lineItems", [{"itemCode": ITEM, "quantity": 1}])["signedSnapshot"]
        data = step("subtotal", {})
        snapshot, total = data["signedSnapshot"], data["balanceAmount"]
        snapshot = step("payments", [{"paymentCode": "01", "amount": total}])["signedSnapshot"]
        billed = step("bill", {"seq": number, "receiptCounter": number, "transactionDatetime": now})
        assert billed["transactionNo"] == number
    return total


def _final_record(wait_for, headers, tenant_id):
    def final():
        with _client("URL_REPORT") as c:
            resp = c.get(f"/api/v1/tenants/{tenant_id}/stores/{STORE}/settlements", headers=headers, params={"terminal_no": 1})
        rows = resp.json().get("data") or []
        return rows if rows and rows[0]["state"] == "final" else None

    return wait_for(final, timeout=20.0, description="the settlement to become final")[0]


@pytest.mark.asyncio
async def test_carried_numbers_missing_on_the_way_are_named(wait_for):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _setup(tenant_id)
    _open(terminal_id, api_key)

    totals = [_carried_sale(terminal_id, api_key, n) for n in (1, 2, 4)]  # 3 was lost on the way

    def arrived():
        resp = _report(headers, tenant_id, "flash", terminal_no=1)
        return resp.status_code == 200 and (resp.json().get("data") or {}).get("salesGross", {}).get("count") == 3

    wait_for(arrived, timeout=20.0, description="the three sales in report")

    expected = FLOAT + sum(totals)
    with _client("URL_TERMINAL") as c:
        closed = c.post(f"/api/v1/terminals/{terminal_id}/close", json={"physicalAmount": expected, "seq": 5},
                        headers={"X-API-KEY": api_key})
    assert closed.status_code == 200, closed.text
    data = closed.json()["data"]
    assert data["missingCount"] == 2
    assert data["expectedCashTotal"] == expected and data["difference"] == 0
    receipt = json.loads(data["receiptText"])
    columns = {
        e["columns"][0]["value"]: e["columns"][1]["value"] for e in receipt["elements"] if e["type"] == "columns"
    }
    assert columns["未着の取引"] == "2件"

    record = _final_record(wait_for, headers, tenant_id)
    assert record["declaredCount"] == 5 and record["declaredSource"] == "pos"
    assert record["includedCount"] == 3 and record["serverNumberedCount"] == 0
    assert record["includedRanges"] == [{"first": 1, "last": 2}, {"first": 4, "last": 4}]
    assert record["missingRanges"] == [{"first": 3, "last": 3}, {"first": 5, "last": 5}]
    assert record["duplicateNumbers"] == []

    store_daily = _report(headers, tenant_id, "daily")
    assert store_daily.status_code == 200, store_daily.text
    report = store_daily.json()["data"]
    assert report["missingCount"] == 2
    assert [(r["terminalNo"], r["first"], r["last"]) for r in report["missingRanges"]] == [(1, 3, 3), (1, 5, 5)]
    assert report["salesGross"]["count"] == 3


def _docker(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)


def _report_container_running() -> bool:
    if shutil.which("docker") is None:
        return False
    result = _docker("inspect", "-f", "{{.State.Running}}", REPORT_CONTAINER)
    return result.returncode == 0 and result.stdout.strip() == "true"


@pytest.mark.asyncio
@pytest.mark.skipif(not _report_container_running(), reason="needs the docker-compose stack's report container")
async def test_a_close_is_refused_while_report_is_away_and_goes_through_after(wait_for):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _setup(tenant_id)
    _open(terminal_id, api_key)
    key = {"X-API-KEY": api_key}

    # Paused, not stopped: its Dapr sidecar shares its network namespace and
    # stays attached, so the stack is as it was once it is resumed
    assert _docker("pause", REPORT_CONTAINER).returncode == 0
    try:
        with _client("URL_TERMINAL") as c:
            c.timeout = 60.0  # terminal waits up to 30 s for report
            refused = c.post(f"/api/v1/terminals/{terminal_id}/close", json={"physicalAmount": FLOAT}, headers=key)
    finally:
        assert _docker("unpause", REPORT_CONTAINER).returncode == 0

    assert refused.status_code == 503, refused.text
    assert refused.json()["userError"]["code"] == "406016"
    with _client("URL_TERMINAL") as c:
        info = c.get(f"/api/v1/terminals/{terminal_id}", headers=key).json()["data"]
    assert info["status"] == "Opened"

    def report_back():
        with _client("URL_REPORT") as c:
            try:
                return c.get("/health").status_code == 200
            except Exception:  # noqa: BLE001 - still waking up
                return False

    wait_for(report_back, timeout=30.0, description="report to answer again")
    with _client("URL_TERMINAL") as c:
        closed = c.post(f"/api/v1/terminals/{terminal_id}/close", json={"physicalAmount": FLOAT}, headers=key)
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["expectedCashTotal"] == FLOAT
    record = _final_record(wait_for, headers, tenant_id)
    assert record["expectedCash"]["total"] == FLOAT and record["difference"] == 0

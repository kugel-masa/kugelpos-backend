# Copyright 2026 masa@kugel
"""Settlement journey e2e (#343): a close confirms the settlement in report, and
the daily reports answer from it.

  1. Tenant, masters, store, terminal; sign in and open with a float
  2. Two cash sales and a cash-in; wait until report has them (flash)
  3. Close preview: nothing stored, the figures report would settle
  4. Close with the counted cash. This cart path numbers transactions on the
     server (no carried snapshot), so the client declares no seq (R-13)
  5. Wait for the settlement to become final (its close log reached report)
  6. Terminal and store daily reports equal the frozen settlement
"""
import pytest

from .test_pos_full_journey import _admin_token, _app_business_date, _client, _new_tenant_id, _post

STORE = "5343"
ITEM = "ITEM-SETTLE"


def _setup(tenant_id: str) -> tuple[dict, str, str]:
    token = _admin_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}
    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Settlement Tenant", "stores": [], "tags": ["e2e-settlement"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Settlement Staff", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "Default", "descriptionShort": "D", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": ITEM, "description": "Settlement Item", "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001", "itemDetails": [], "imageUrls": [],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash", "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": True, "canChange": True, "isActive": True,
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": STORE, "store_name": "Settlement Store", "tags": [],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/stores/{STORE}/items", headers,
          json={"itemCode": ITEM, "storePrice": 100.0}, ok=(200, 201, 400, 404))
    with _client("URL_TERMINAL") as c:
        resp = c.post("/api/v1/terminals", json={"store_code": STORE, "terminal_no": 1, "description": "T1"}, headers=headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
    return headers, data["terminalId"], data["apiKey"]


def _sell(tenant_id: str, terminal_id: str, api_key: str) -> float:
    key = {"X-API-KEY": api_key}
    q = f"?terminal_id={terminal_id}"
    with _client("URL_CART") as c:
        cart_id = c.post(f"/api/v1/carts{q}", headers=key, json={
            "tenant_id": tenant_id, "terminal_id": terminal_id, "operator_code": "S001", "operator_name": "Staff",
        }).json()["data"]["cartId"]
        assert c.post(f"/api/v1/carts/{cart_id}/lineItems{q}", headers=key, json=[{"itemCode": ITEM, "quantity": 1}]).status_code == 200
        balance = c.post(f"/api/v1/carts/{cart_id}/subtotal{q}", headers=key).json()["data"]["balanceAmount"]
        assert c.post(f"/api/v1/carts/{cart_id}/payments{q}", headers=key, json=[{"paymentCode": "01", "amount": balance}]).status_code == 200
        assert c.post(f"/api/v1/carts/{cart_id}/bill{q}", headers=key).status_code == 200
    return balance


def _report(headers: dict, tenant_id: str, scope: str, terminal_no=None):
    path = f"/api/v1/tenants/{tenant_id}/stores/{STORE}" + (f"/terminals/{terminal_no}" if terminal_no else "") + "/reports"
    with _client("URL_REPORT") as c:
        return c.get(path, headers=headers, params={
            "report_scope": scope, "report_type": "sales", "business_date": _app_business_date(),
        })


@pytest.mark.asyncio
async def test_close_confirms_the_settlement_and_daily_reports_answer_from_it(wait_for):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _setup(tenant_id)
    key = {"X-API-KEY": api_key}

    with _client("URL_TERMINAL") as c:
        assert c.post(f"/api/v1/terminals/{terminal_id}/sign-in", json={"staff_id": "S001"}, headers=key).status_code == 200
        assert c.post(f"/api/v1/terminals/{terminal_id}/open", json={"initial_amount": 10000.0}, headers=key).status_code == 200

    takings = _sell(tenant_id, terminal_id, api_key) + _sell(tenant_id, terminal_id, api_key)
    with _client("URL_TERMINAL") as c:
        assert c.post(f"/api/v1/terminals/{terminal_id}/cash-in", json={"amount": 500.0, "description": "e2e"}, headers=key).status_code == 200
    expected = 10000.0 + takings + 500.0

    # Report has both sales and the cash movements before the close (flash is live)
    def _flash_has_everything():
        resp = _report(headers, tenant_id, "flash", terminal_no=1)
        data = resp.json().get("data") or {}
        return resp.status_code == 200 and data.get("salesGross", {}).get("count") == 2 and data.get("cash", {}).get("logicalAmount") == expected

    wait_for(_flash_has_everything, timeout=20.0, description="sales and cash logs in report")

    # Preview: nothing stored
    with _client("URL_TERMINAL") as c:
        preview = c.get(f"/api/v1/terminals/{terminal_id}/close-preview", headers=key)
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["expectedCashTotal"] == expected
    assert preview.json()["data"]["missingCount"] == 0
    assert preview.json()["data"]["settled"] is False

    with _client("URL_TERMINAL") as c:
        closed = c.post(f"/api/v1/terminals/{terminal_id}/close", json={"physicalAmount": expected}, headers=key)
    assert closed.status_code == 200, closed.text
    data = closed.json()["data"]
    assert data["expectedCashTotal"] == expected
    assert data["difference"] == 0
    assert data["missingCount"] == 0
    assert "あるべき現金" in data["receiptText"]
    assert "未着" not in data["receiptText"]
    settlement_id = data["settlementId"]

    # The settlement becomes final once its close log reaches report
    def _final():
        with _client("URL_REPORT") as c:
            resp = c.get(f"/api/v1/tenants/{tenant_id}/stores/{STORE}/settlements", headers=headers, params={"terminal_no": 1})
        rows = resp.json().get("data") or []
        return rows if rows and rows[0]["state"] == "final" else None

    rows = wait_for(_final, timeout=20.0, description="the settlement to become final")
    assert rows[0]["settlementId"] == settlement_id
    assert rows[0]["includedCount"] == 2
    assert rows[0]["serverNumberedCount"] == 2
    assert rows[0]["declaredSource"] == "none"
    assert rows[0]["expectedCash"]["total"] == expected

    terminal_daily = _report(headers, tenant_id, "daily", terminal_no=1)
    store_daily = _report(headers, tenant_id, "daily")
    for resp in (terminal_daily, store_daily):
        assert resp.status_code == 200, resp.text
        daily = resp.json()["data"]
        assert daily["salesGross"]["count"] == 2
        assert daily["cash"]["logicalAmount"] == expected
        assert daily["cash"]["physicalAmount"] == expected
        assert daily["missingCount"] == 0

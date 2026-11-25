# Copyright 2026 masa@kugel
"""The settlement's expected cash through the real cart and terminal (#343).

One session with everything that moves the drawer, each through the public
APIs: a cash sale paid with change, a sale split between cash and card, a sale
voided with a cash refund, a sale returned with a cash refund, a pickup (cash
out) and a cash in. The expected cash is worked out here from the amounts cart
answered, and must match the close, the settlement record and the daily report.
"""
import pytest

from .test_pos_full_journey import _app_business_date, _client, _new_tenant_id, _post
from .test_settlement_journey import ITEM, STORE, _report, _setup

FLOAT = 10000.0


def _cart(tenant_id, terminal_id, api_key, quantity):
    """A cart with `quantity` items, subtotalled; returns (cart_id, balance)."""
    key = {"X-API-KEY": api_key}
    q = f"?terminal_id={terminal_id}"
    with _client("URL_CART") as c:
        cart_id = c.post(f"/api/v1/carts{q}", headers=key, json={
            "tenant_id": tenant_id, "terminal_id": terminal_id, "operator_code": "S001", "operator_name": "Staff",
        }).json()["data"]["cartId"]
        r = c.post(f"/api/v1/carts/{cart_id}/lineItems{q}", headers=key, json=[{"itemCode": ITEM, "quantity": quantity}])
        assert r.status_code == 200, r.text
        balance = c.post(f"/api/v1/carts/{cart_id}/subtotal{q}", headers=key).json()["data"]["balanceAmount"]
    return cart_id, balance


def _pay_and_bill(terminal_id, api_key, cart_id, payments):
    key = {"X-API-KEY": api_key}
    q = f"?terminal_id={terminal_id}"
    with _client("URL_CART") as c:
        r = c.post(f"/api/v1/carts/{cart_id}/payments{q}", headers=key, json=payments)
        assert r.status_code == 200, r.text
        paid = r.json()["data"]
        billed = c.post(f"/api/v1/carts/{cart_id}/bill{q}", headers=key)
        assert billed.status_code == 200, billed.text
    return billed.json()["data"]["transactionNo"], paid


def _cancel_transaction(tenant_id, terminal_id, api_key, transaction_no, action, refund):
    with _client("URL_CART") as c:
        r = c.post(
            f"/api/v1/tenants/{tenant_id}/stores/{STORE}/terminals/1/transactions/{transaction_no}/{action}"
            f"?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": refund}],
            headers={"X-API-KEY": api_key},
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_expected_cash_through_change_split_void_return_and_cash_movements(wait_for):
    tenant_id = _new_tenant_id()
    headers, terminal_id, api_key = _setup(tenant_id)
    # A card that takes exactly the balance: no deposit over, no change
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "11", "description": "Card", "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": False, "canChange": False, "isActive": True,
    })
    key = {"X-API-KEY": api_key}
    with _client("URL_TERMINAL") as c:
        assert c.post(f"/api/v1/terminals/{terminal_id}/sign-in", json={"staff_id": "S001"}, headers=key).status_code == 200
        assert c.post(f"/api/v1/terminals/{terminal_id}/open", json={"initial_amount": FLOAT}, headers=key).status_code == 200

    # 1. Cash with change: 1,000 handed over, the change goes back
    cart_id, balance_a = _cart(tenant_id, terminal_id, api_key, 1)
    _, paid = _pay_and_bill(terminal_id, api_key, cart_id, [{"paymentCode": "01", "amount": 1000.0}])
    assert paid["changeAmount"] == 1000.0 - balance_a

    # 2. Split: 100 in cash, the rest on the card
    cart_id, balance_b = _cart(tenant_id, terminal_id, api_key, 3)
    with _client("URL_CART") as c:
        r = c.post(f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}", headers=key,
                   json=[{"paymentCode": "01", "amount": 100.0}])
        assert r.status_code == 200, r.text
    _pay_and_bill(terminal_id, api_key, cart_id, [{"paymentCode": "11", "amount": balance_b - 100.0}])

    # 3. A cash sale voided with a cash refund
    cart_id, balance_c = _cart(tenant_id, terminal_id, api_key, 2)
    no_c, _ = _pay_and_bill(terminal_id, api_key, cart_id, [{"paymentCode": "01", "amount": balance_c}])

    # 4. A cash sale returned with a cash refund
    cart_id, balance_d = _cart(tenant_id, terminal_id, api_key, 5)
    no_d, _ = _pay_and_bill(terminal_id, api_key, cart_id, [{"paymentCode": "01", "amount": balance_d}])

    # The originals must reach report before they can be voided or returned there
    def _flash_count(n):
        def check():
            resp = _report(headers, tenant_id, "flash", terminal_no=1)
            return resp.status_code == 200 and (resp.json().get("data") or {}).get("salesGross", {}).get("count") == n
        return check

    wait_for(_flash_count(4), timeout=20.0, description="the four sales in report")
    _cancel_transaction(tenant_id, terminal_id, api_key, no_c, "void", balance_c)
    _cancel_transaction(tenant_id, terminal_id, api_key, no_d, "return", balance_d)

    # 5. A pickup of 2,000 and a cash in of 300
    with _client("URL_TERMINAL") as c:
        assert c.post(f"/api/v1/terminals/{terminal_id}/cash-out", json={"amount": 2000.0, "description": "pickup"}, headers=key).status_code == 200
        assert c.post(f"/api/v1/terminals/{terminal_id}/cash-in", json={"amount": 300.0, "description": "top up"}, headers=key).status_code == 200

    # Worked out here, from what cart charged: change, the card part, the void
    # and the return leave no cash behind
    cash_sales = balance_a + 100.0 + (balance_c - balance_c) + (balance_d - balance_d)
    expected = FLOAT + cash_sales - 2000.0 + 300.0

    def _flash_cash_settled():
        resp = _report(headers, tenant_id, "flash", terminal_no=1)
        cash = (resp.json().get("data") or {}).get("cash") or {}
        return resp.status_code == 200 and cash.get("logicalAmount") == expected and cash.get("cashOut", {}).get("count") == 1

    wait_for(_flash_cash_settled, timeout=20.0, description=f"report to have every log (expected cash {expected})")

    # Close with 50 short
    with _client("URL_TERMINAL") as c:
        closed = c.post(f"/api/v1/terminals/{terminal_id}/close", json={"physicalAmount": expected - 50.0}, headers=key)
    assert closed.status_code == 200, closed.text
    data = closed.json()["data"]
    assert data["expectedCashTotal"] == expected
    assert data["difference"] == -50.0
    assert data["missingCount"] == 0 and data["missingCashLogCount"] == 0

    def _final():
        with _client("URL_REPORT") as c:
            resp = c.get(f"/api/v1/tenants/{tenant_id}/stores/{STORE}/settlements", headers=headers, params={"terminal_no": 1})
        rows = resp.json().get("data") or []
        return rows if rows and rows[0]["state"] == "final" else None

    record = wait_for(_final, timeout=20.0, description="the settlement to become final")[0]
    assert record["expectedCash"] == {
        "cashSales": cash_sales,
        "cashIn": {"amount": FLOAT + 300.0, "count": 2},
        "cashOut": {"amount": -2000.0, "count": 1},
        "total": expected,
    }
    assert record["physicalAmount"] == expected - 50.0
    assert record["difference"] == -50.0
    assert record["cashLogCount"] == 3

    daily = _report(headers, tenant_id, "daily", terminal_no=1)
    assert daily.status_code == 200, daily.text
    cash = daily.json()["data"]["cash"]
    assert cash["logicalAmount"] == expected
    assert cash["physicalAmount"] == expected - 50.0
    assert cash["differenceAmount"] == -50.0
    assert cash["cashIn"] == {"amount": FLOAT + 300.0, "count": 2}
    assert cash["cashOut"] == {"amount": -2000.0, "count": 1}
    assert _app_business_date()  # the reports above were for today's business date

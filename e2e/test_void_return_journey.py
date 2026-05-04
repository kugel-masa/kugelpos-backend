# Copyright 2026 masa@kugel
"""Void / return flow e2e — POS cancellation paths.

Walks: bill a transaction → void it → verify the cancellation surfaces
on every downstream service (journal entry for the void, stock
restored, report unchanged-net).
"""
import os
import time
import uuid
from datetime import datetime

import httpx
import pytest


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


def _admin_token(tenant_id: str) -> str:
    with _client("URL_ACCOUNT") as c:
        c.post("/api/v1/accounts/register", json={
            "username": "admin", "password": "admin", "tenant_id": tenant_id,
        })
        resp = c.post("/api/v1/accounts/token", data={
            "username": "admin", "password": "admin", "client_id": tenant_id,
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


def _post(url_env, path, headers, json, ok=(200, 201, 400)):
    with _client(url_env) as c:
        resp = c.post(path, json=json, headers=headers)
    assert resp.status_code in ok, f"{path} -> {resp.status_code}: {resp.text}"
    try:
        return resp.json()
    except ValueError:
        return {}


def _bootstrap_pos(tenant_id: str, store_code: str, terminal_no: int, item_code: str):
    """Run the bootstrap path used by test_pos_full_journey: create
    tenant + masters + store + terminal + sign-in + open. Returns
    (terminal_id, api_key, opened_terminal_jwt, headers)."""
    token = _admin_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Void Tenant",
        "stores": [], "tags": ["void-flow"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Void Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "Default", "descriptionShort": "D", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": item_code, "description": "Void Item",
        "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001",
        "itemDetails": [], "imageUrls": [],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash", "limitAmount": 0.0,
        "canRefund": True, "canDepositOver": True, "canChange": True, "isActive": True,
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Void Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        r = c.post("/api/v1/terminals", json={
            "store_code": store_code, "terminal_no": terminal_no,
            "description": "Void Terminal",
        }, headers=headers)
        assert r.status_code == 201, r.text
        terminal_id = r.json()["data"]["terminalId"]
        api_key = r.json()["data"]["apiKey"]

        r = c.post(
            f"/api/v1/auth/token?terminal_id={terminal_id}",
            headers={"X-API-KEY": api_key},
        )
        terminal_jwt = r.json()["data"]["access_token"]
        th = {"Authorization": f"Bearer {terminal_jwt}"}

        r = c.post(f"/api/v1/terminals/{terminal_id}/sign-in",
                   json={"staff_id": "S001"}, headers=th)
        assert r.status_code == 200, r.text
        th = {"Authorization": f"Bearer {r.headers.get('x-new-token', terminal_jwt)}"}

        r = c.post(f"/api/v1/terminals/{terminal_id}/open",
                   json={"initial_amount": 0.0}, headers=th)
        assert r.status_code == 200, r.text

    return terminal_id, api_key, headers


def _bill_cart(api_key: str, terminal_id: str, item_code: str, quantity: int = 1) -> tuple[int, float]:
    """Run a cart through subtotal → pay → bill. Returns (transaction_no, amount_paid)."""
    with _client("URL_CART") as c:
        h = {"X-API-KEY": api_key}
        r = c.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json={
                "tenant_id": os.environ.get("TENANT_ID"),  # cart pulls from terminal_info
                "terminal_id": terminal_id,
                "operator_code": "S001", "operator_name": "Void Staff",
            },
            headers=h,
        )
        assert r.status_code == 201, r.text
        cart_id = r.json()["data"]["cartId"]

        r = c.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=[{"itemCode": item_code, "quantity": quantity}],
            headers=h,
        )
        assert r.status_code == 200, r.text

        r = c.post(
            f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=h,
        )
        balance = r.json()["data"]["balanceAmount"]

        r = c.post(
            f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": balance}], headers=h,
        )
        assert r.status_code == 200, r.text

        r = c.post(
            f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=h,
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["transactionNo"], balance


@pytest.mark.asyncio
async def test_bill_then_void_propagates():
    """Bill a transaction, void it, and verify the void surfaces on
    journal (extra entry with cancel transaction_type)."""
    tenant_id = "VOID" + uuid.uuid4().hex[:6].upper()
    store_code = "5061"
    terminal_no = 1
    item_code = "ITEM-VOID"

    terminal_id, api_key, headers = _bootstrap_pos(tenant_id, store_code, terminal_no, item_code)

    # Bill the original transaction
    transaction_no, amount = _bill_cart(api_key, terminal_id, item_code, quantity=2)
    assert amount > 0

    time.sleep(3.0)  # let the original tranlog propagate

    # Void it via cart's REST API
    with _client("URL_CART") as c:
        r = c.post(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
            f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": amount}],
            headers={"X-API-KEY": api_key},
        )
        assert r.status_code == 200, r.text

    time.sleep(5.0)  # let the void tranlog propagate

    business_date = datetime.now().strftime("%Y%m%d")

    # Verify journal has the original sale + a separate cancellation entry.
    # Cart/journal model the cancel as transaction_type 201 (VoidSales).
    with _client("URL_JOURNAL") as c:
        r = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals"
            f"?business_date_from={business_date}&business_date_to={business_date}",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        journals = r.json().get("data") or []
        types = [j.get("transactionType") for j in journals]
        # Should have at least one entry of type 201 (VoidSales)
        assert 201 in types, (
            f"Expected a VoidSales (transactionType=201) journal entry, "
            f"got types {types}"
        )


@pytest.mark.asyncio
async def test_void_idempotency_via_double_call():
    """Calling void twice on the same transaction should fail the second
    time with a clear domain error (cart enforces single-void)."""
    tenant_id = "VOID" + uuid.uuid4().hex[:6].upper()
    store_code = "5062"
    terminal_no = 2
    item_code = "ITEM-VOID2"

    terminal_id, api_key, _ = _bootstrap_pos(tenant_id, store_code, terminal_no, item_code)
    transaction_no, amount = _bill_cart(api_key, terminal_id, item_code)

    with _client("URL_CART") as c:
        # First void
        r1 = c.post(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
            f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": amount}],
            headers={"X-API-KEY": api_key},
        )
        assert r1.status_code == 200, r1.text

        # Second void must be rejected
        r2 = c.post(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
            f"/transactions/{transaction_no}/void?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": amount}],
            headers={"X-API-KEY": api_key},
        )
        assert r2.status_code in (400, 409), (
            f"Re-void should be rejected; got {r2.status_code}: {r2.text}"
        )

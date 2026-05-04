# Copyright 2026 masa@kugel
"""Concurrency e2e — spawn N parallel cart-bill flows on the same
terminal and verify the per-terminal counters stay consistent.

The cart counter (transaction_no, receipt_no) is updated via Mongo's
findAndModify aggregation pipeline, which is supposed to be atomic.
This test stresses that path under contention to catch regressions
in either the repository or the cart state machine.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import httpx
import pytest


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=60.0)


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


def _bootstrap(tenant_id, store_code, terminal_no, item_code):
    """Set up tenant + masters + store + terminal, sign in, open."""
    token = _admin_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Concurrency",
        "stores": [], "tags": ["concurrency"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Concurrency", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "D", "descriptionShort": "D", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": item_code, "description": "Concurrency Item",
        "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001",
        "itemDetails": [], "imageUrls": [],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash", "limitAmount": 0.0,
        "canRefund": True, "canDepositOver": True, "canChange": True, "isActive": True,
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Concurrency Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        r = c.post("/api/v1/terminals", json={
            "store_code": store_code, "terminal_no": terminal_no,
            "description": "Concurrency Terminal",
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

    return terminal_id, api_key


def _run_cart(terminal_id, api_key, item_code) -> tuple[int, float]:
    """One worker: create cart → add item → subtotal → pay → bill.

    Returns (transaction_no, balance_paid)."""
    h = {"X-API-KEY": api_key}
    with _client("URL_CART") as c:
        r = c.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json={
                "tenant_id": os.environ.get("TENANT_ID"),
                "terminal_id": terminal_id,
                "operator_code": "S001", "operator_name": "Concurrency Worker",
            },
            headers=h,
        )
        assert r.status_code == 201, r.text
        cart_id = r.json()["data"]["cartId"]

        r = c.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=[{"itemCode": item_code, "quantity": 1}],
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
async def test_parallel_carts_get_unique_transaction_nos():
    """N parallel carts on the same terminal should each get a UNIQUE
    transaction_no — proving the terminal_counter atomic increment
    holds up under contention."""
    tenant_id = "CCY" + uuid.uuid4().hex[:8].upper()
    store_code = "5070"
    terminal_no = 1
    item_code = "ITEM-CCY"
    n_workers = 8

    terminal_id, api_key = _bootstrap(tenant_id, store_code, terminal_no, item_code)

    transaction_nos = []
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [
            pool.submit(_run_cart, terminal_id, api_key, item_code)
            for _ in range(n_workers)
        ]
        for fut in as_completed(futures):
            tno, _ = fut.result()
            transaction_nos.append(tno)

    assert len(transaction_nos) == n_workers
    # Critical: every transaction_no is unique
    assert len(set(transaction_nos)) == n_workers, (
        f"Duplicate transaction_no detected under concurrency: {transaction_nos}"
    )
    # And they form a contiguous range (no gaps from race conditions)
    transaction_nos.sort()
    assert transaction_nos[-1] - transaction_nos[0] == n_workers - 1, (
        f"transaction_nos should be contiguous; got {transaction_nos}"
    )

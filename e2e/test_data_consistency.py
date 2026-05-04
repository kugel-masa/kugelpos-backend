# Copyright 2026 masa@kugel
"""Cross-service data consistency e2e.

After a single cart checkout, the same tranlog must be visible (in the
expected shape) on every downstream subscriber:
  * journal — POST /journals row
  * report  — flash sales aggregate non-zero
  * stock   — current_quantity decremented for the sold item

This test isolates the "fan-out happened correctly" property. The full
POS journey test verifies the happy path; this one specifically watches
every service for the same transaction in one place.
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


@pytest.mark.asyncio
async def test_bill_propagates_to_journal_report_stock():
    """After a cart bill, the same transaction must surface on journal,
    report, and stock within ~5 s of pub/sub propagation."""
    tenant_id = "DCY" + uuid.uuid4().hex[:8].upper()
    store_code = "5050"
    terminal_no = 1
    item_code = "ITEM-DCY"
    initial_qty = 50.0
    purchase_qty = 3

    # Bootstrap: tenant fan-out, masters, store, terminal, JWT, sign-in, open
    token = _admin_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Consistency",
        "stores": [], "tags": ["e2e-consistency"],
    })

    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Consistency Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "Default", "descriptionShort": "D", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": item_code, "description": "Consistency Item",
        "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001",
        "itemDetails": [], "imageUrls": [],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash",
        "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": True, "canChange": True, "isActive": True,
    })

    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Consistency Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        resp = c.post("/api/v1/terminals", json={
            "store_code": store_code, "terminal_no": terminal_no,
            "description": "Consistency Terminal",
        }, headers=headers)
        assert resp.status_code == 201, resp.text
        terminal_id = resp.json()["data"]["terminalId"]
        api_key = resp.json()["data"]["apiKey"]

    # Seed initial stock via PUT (not POST — /update is a PUT route).
    with _client("URL_STOCK") as c:
        resp = c.put(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update",
            json={
                "quantityChange": initial_qty,
                "updateType": "initial",
                "operatorId": "admin",
                "note": "consistency-test seed",
            },
            headers=headers,
        )
        assert resp.status_code in (200, 201), resp.text

    # Get terminal JWT, sign in, open
    with _client("URL_TERMINAL") as c:
        resp = c.post(
            f"/api/v1/auth/token?terminal_id={terminal_id}",
            headers={"X-API-KEY": api_key},
        )
        terminal_jwt = resp.json()["data"]["access_token"]
        term_headers = {"Authorization": f"Bearer {terminal_jwt}"}

        resp = c.post(f"/api/v1/terminals/{terminal_id}/sign-in",
                      json={"staff_id": "S001"}, headers=term_headers)
        assert resp.status_code == 200, resp.text
        signed_jwt = resp.headers.get("x-new-token", terminal_jwt)
        signed_headers = {"Authorization": f"Bearer {signed_jwt}"}

        resp = c.post(f"/api/v1/terminals/{terminal_id}/open",
                      json={"initial_amount": 0.0}, headers=signed_headers)
        assert resp.status_code == 200, resp.text

    # Cart checkout
    with _client("URL_CART") as c:
        resp = c.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json={
                "tenant_id": tenant_id, "terminal_id": terminal_id,
                "operator_code": "S001", "operator_name": "Consistency Staff",
            },
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 201, resp.text
        cart_id = resp.json()["data"]["cartId"]

        resp = c.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=[{"itemCode": item_code, "quantity": purchase_qty}],
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text

        resp = c.post(
            f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
            headers={"X-API-KEY": api_key},
        )
        balance = resp.json()["data"]["balanceAmount"]

        resp = c.post(
            f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": balance}],
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text

        resp = c.post(
            f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text
        transaction_no = resp.json()["data"]["transactionNo"]

    # Wait for fan-out
    time.sleep(6.0)

    business_date = datetime.now().strftime("%Y%m%d")

    # 1. journal has the entry
    with _client("URL_JOURNAL") as c:
        resp = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals"
            f"?business_date_from={business_date}&business_date_to={business_date}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert any(
            j.get("transactionNo") == transaction_no
            for j in (resp.json().get("data") or [])
        ), "journal missing transaction"

    # 2. report sees non-zero sales for the store on this business date
    with _client("URL_REPORT") as c:
        resp = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
            params={
                "report_scope": "flash", "report_type": "sales",
                "business_date": business_date, "open_counter": 1,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        report = resp.json().get("data") or {}
        sales_gross = report.get("salesGross") or report.get("sales_gross") or {}
        assert sales_gross.get("amount", 0) >= balance, (
            f"report sales_gross {sales_gross} below cart balance {balance}"
        )

    # 3. stock decremented by purchase_qty (initial_qty - purchase_qty)
    with _client("URL_STOCK") as c:
        resp = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        current = resp.json()["data"].get("currentQuantity")
        assert current is not None, resp.text
        assert current == initial_qty - purchase_qty, (
            f"Stock should be {initial_qty - purchase_qty} after selling "
            f"{purchase_qty} from {initial_qty}, got {current}"
        )

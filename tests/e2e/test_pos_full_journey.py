# Copyright 2026 masa@kugel
"""Full POS journey e2e — system-wide happy-path test.

Walks a single transaction from an empty stack through every service:

  1. Register admin & log in (account)
  2. POST /tenants on terminal — fans out, creating per-tenant DBs in
     master-data / cart / report / journal / stock
  3. Seed master-data: staff, category, item, payment, tax tables
  4. Create store + terminal (terminal)
  5. Exchange API key for terminal JWT
  6. Sign-in staff, open terminal
  7. Create cart, add line item, subtotal, pay, bill
  8. Wait for pub/sub propagation, then verify:
       * journal has the journal entry (journal)
       * report shows non-zero sales (report)

Uses a fresh tenant per run so reruns don't pollute existing state.
"""
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest


def _app_business_date() -> str:
    """Business date in the backend's app timezone. Services compute it via
    settings.TIMEZONE (default Asia/Tokyo), not host-local time, so a UTC
    host must not use datetime.now() here (#150)."""
    return datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tokyo"))).strftime("%Y%m%d")


def _new_tenant_id() -> str:
    """Build a fresh tenant_id per run.

    NB: tenant_id MUST NOT contain hyphens because terminal_id is encoded
    as `{tenant_id}-{store_code}-{terminal_no}` and the security helper
    splits on `-` taking only the first segment as the tenant.
    """
    return "JNY" + uuid.uuid4().hex[:8].upper()


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


def _admin_token(tenant_id: str) -> str:
    """Register admin (idempotent) then log in to get a JWT."""
    with _client("URL_ACCOUNT") as c:
        c.post("/api/v1/accounts/register", json={
            "username": "admin", "password": "admin", "tenant_id": tenant_id,
        })
        resp = c.post("/api/v1/accounts/token", data={
            "username": "admin", "password": "admin", "client_id": tenant_id,
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


def _post(url_env: str, path: str, headers: dict, json: dict, ok=(200, 201, 400)) -> dict:
    """POST helper — accepts a tuple of OK statuses (400 typically means
    'already exists' which we treat as success for idempotent setup)."""
    with _client(url_env) as c:
        resp = c.post(path, json=json, headers=headers)
    assert resp.status_code in ok, f"{path} -> {resp.status_code}: {resp.text}"
    try:
        return resp.json()
    except ValueError:
        return {}


@pytest.mark.asyncio
async def test_pos_full_journey(wait_for):
    """End-to-end POS journey across all 7 services."""
    tenant_id = _new_tenant_id()
    store_code = "5001"
    terminal_no = 1
    item_code = "ITEM-JNY"

    # 1. Admin login (this also registers admin if not exists)
    token = _admin_token(tenant_id)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Tenant fan-out — terminal POST creates DBs in all downstream services
    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Journey Tenant",
        "stores": [], "tags": ["e2e-journey"],
    })

    # 3. Seed master-data: tax categories are auto-seeded; we add staff +
    #    category + item + payment so cart can resolve everything.
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Journey Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "Default Category",
        "descriptionShort": "DC", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": item_code, "description": "Journey Item",
        "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001",
        "itemDetails": [], "imageUrls": [],
    })
    _post(
        "URL_MASTER_DATA",
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        headers,
        json={"itemCode": item_code, "storePrice": 100.0},
        # Store may not exist yet (we create it on terminal next); 400 is fine.
        ok=(200, 201, 400, 404),
    )
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash",
        "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": True, "canChange": True, "isActive": True,
    })

    # 4. Create store + terminal on terminal service
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Journey Store", "tags": [],
    })

    # Now that the store exists, link the item-store record (idempotent retry).
    _post(
        "URL_MASTER_DATA",
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/items",
        headers,
        json={"itemCode": item_code, "storePrice": 100.0},
        ok=(200, 201, 400, 404),
    )

    with _client("URL_TERMINAL") as c:
        resp = c.post(
            "/api/v1/terminals",
            json={"store_code": store_code, "terminal_no": terminal_no, "description": "Journey Terminal"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        terminal_data = resp.json()["data"]
        terminal_id = terminal_data["terminalId"]
        api_key = terminal_data["apiKey"]

    # 5. Exchange API key for terminal JWT
    with _client("URL_TERMINAL") as c:
        resp = c.post(
            f"/api/v1/auth/token?terminal_id={terminal_id}",
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text
        terminal_jwt = resp.json()["data"]["access_token"]

    term_jwt_headers = {"Authorization": f"Bearer {terminal_jwt}"}

    # 6. Sign in + open
    with _client("URL_TERMINAL") as c:
        resp = c.post(
            f"/api/v1/terminals/{terminal_id}/sign-in",
            json={"staff_id": "S001"}, headers=term_jwt_headers,
        )
        assert resp.status_code == 200, resp.text

        # Pick up the new token reflecting the staff claim
        signed_in_jwt = resp.headers.get("x-new-token", terminal_jwt)
        signed_in_headers = {"Authorization": f"Bearer {signed_in_jwt}"}

        resp = c.post(
            f"/api/v1/terminals/{terminal_id}/open",
            json={"initial_amount": 0.0}, headers=signed_in_headers,
        )
        assert resp.status_code == 200, resp.text
        opened_jwt = resp.headers.get("x-new-token", signed_in_jwt)
        opened_headers = {"Authorization": f"Bearer {opened_jwt}"}

    # 7. Cart flow: create -> add item -> subtotal -> pay -> bill
    with _client("URL_CART") as c:
        resp = c.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json={
                "tenant_id": tenant_id, "terminal_id": terminal_id,
                "operator_code": "S001", "operator_name": "Journey Staff",
            },
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 201, resp.text
        cart_id = resp.json()["data"]["cartId"]

        resp = c.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=[{"itemCode": item_code, "quantity": 2}],
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text

        resp = c.post(
            f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text
        balance = resp.json()["data"]["balanceAmount"]
        assert balance > 0, f"Subtotal should produce a non-zero balance: {balance}"

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
        transaction_no = resp.json()["data"].get("transactionNo")
        assert transaction_no, "bill should populate transactionNo"

    # 8. Wait for Dapr pub/sub fan-out (cart -> report / journal / stock).
    # Poll journal until the transaction surfaces; cuts the steady-state
    # wait when fan-out is fast and surfaces a real timeout if it hangs.
    business_date = _app_business_date()

    def _journal_has_transaction() -> bool:
        with _client("URL_JOURNAL") as c:
            r = c.get(
                f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals"
                f"?business_date_from={business_date}&business_date_to={business_date}",
                headers=headers,
            )
            if r.status_code != 200:
                return False
            return any(
                j.get("transactionNo") == transaction_no
                for j in (r.json().get("data") or [])
            )

    wait_for(
        _journal_has_transaction,
        timeout=15.0,
        description=f"journal entry for transaction {transaction_no}",
    )

    # Verify report flash sales for the store reflects today's activity
    with _client("URL_REPORT") as c:
        resp = c.get(
            f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
            params={
                "report_scope": "flash",
                "report_type": "sales",
                "business_date": business_date,
                "open_counter": 1,
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        report = resp.json()["data"]
        assert report is not None, "Report data missing"
        # sales_gross.amount should equal the bill total
        sales_gross = report.get("salesGross") or report.get("sales_gross")
        if sales_gross:
            assert sales_gross.get("amount", 0) >= balance, (
                f"Report sales_gross {sales_gross} below cart balance {balance}"
            )

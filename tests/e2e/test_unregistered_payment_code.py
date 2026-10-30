# Copyright 2026 masa@kugel
"""Paying with a code the tenant has not registered is a 404, not a 500.

Cart has a strategy for "11" (cashless) whatever the tenant has registered.
When master-data has no payment "11", its repository says so with a 404
NotFoundException. The payment strategy re-wrapped that and read a base_url
the repository no longer has, raising AttributeError, and the cart service
wrapped whatever came out of the strategy as a 500. The caller could not
tell a missing payment master from a broken cart.

The cart must also still take a registered payment afterwards.
"""
import os
import uuid

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


def _post(url_env: str, path: str, headers: dict, json: dict, ok=(200, 201, 400)) -> None:
    with _client(url_env) as c:
        resp = c.post(path, json=json, headers=headers)
    assert resp.status_code in ok, f"{path} -> {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_unregistered_payment_code_is_not_found():
    # No hyphen: terminal_id is "{tenant}-{store}-{no}" and is split on "-".
    tenant_id = "PAY" + uuid.uuid4().hex[:8].upper()
    store_code = "5001"
    terminal_no = 1
    item_code = "PAYITEM"

    headers = {"Authorization": f"Bearer {_admin_token(tenant_id)}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Payment Code Tenant",
        "stores": [], "tags": ["e2e-unregistered-payment"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Payment Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "Default Category",
        "descriptionShort": "DC", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": item_code, "description": "Payment Item",
        "unitPrice": 100.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001",
        "itemDetails": [], "imageUrls": [],
    })
    # Only cash is registered; "11" has a cart strategy but no payment master.
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash",
        "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": True, "canChange": True, "isActive": True,
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Payment Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        resp = c.post(
            "/api/v1/terminals",
            json={"store_code": store_code, "terminal_no": terminal_no, "description": "Payment Terminal"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        terminal_id = resp.json()["data"]["terminalId"]
        api_key = resp.json()["data"]["apiKey"]

        resp = c.post(f"/api/v1/auth/token?terminal_id={terminal_id}", headers={"X-API-KEY": api_key})
        assert resp.status_code == 200, resp.text
        jwt = resp.json()["data"]["access_token"]

        resp = c.post(
            f"/api/v1/terminals/{terminal_id}/sign-in",
            json={"staff_id": "S001"}, headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200, resp.text
        jwt = resp.headers.get("x-new-token", jwt)

        resp = c.post(
            f"/api/v1/terminals/{terminal_id}/open",
            json={"initial_amount": 0.0}, headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 200, resp.text

    key_headers = {"X-API-KEY": api_key}
    with _client("URL_CART") as c:
        resp = c.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            json={
                "tenant_id": tenant_id, "terminal_id": terminal_id,
                "operator_code": "S001", "operator_name": "Payment Staff",
            },
            headers=key_headers,
        )
        assert resp.status_code == 201, resp.text
        cart_id = resp.json()["data"]["cartId"]

        resp = c.post(
            f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
            json=[{"itemCode": item_code, "quantity": 1}],
            headers=key_headers,
        )
        assert resp.status_code == 200, resp.text

        resp = c.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=key_headers)
        assert resp.status_code == 200, resp.text
        balance = resp.json()["data"]["balanceAmount"]
        assert balance > 0, resp.text

        resp = c.post(
            f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
            json=[{"paymentCode": "11", "amount": balance}],
            headers=key_headers,
        )
        assert resp.status_code == 404, resp.text
        body = resp.json()
        assert body["code"] == 404, body
        # Error bodies are snake_case (user_error), unlike success bodies.
        assert body["user_error"]["code"] == "100001", body

        # The refused payment left the cart as it was.
        resp = c.post(
            f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
            json=[{"paymentCode": "01", "amount": balance}],
            headers=key_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["balanceAmount"] == 0, resp.text

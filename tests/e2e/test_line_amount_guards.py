# Copyright 2026 masa@kugel
"""A line item cannot be driven to a zero or negative amount.

Nothing checked the quantity, the unit price, or the sign of a discount.
Adding an item with quantity 0 made a line of 0, a negative quantity or price
made a negative line, and a negative fixed discount raised the price. A fixed
discount is checked against the line only when it is added, so lowering the
quantity or the price afterwards drove the line negative (689 x 2 with 1,000
off, then 1 unit: -311).

Each refusal is a 400 with its own code, and leaves the cart as it was.
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


def _assert_refused(resp: httpx.Response, code: str) -> None:
    assert resp.status_code == 400, resp.text
    # Error bodies are snake_case (user_error), unlike success bodies.
    assert resp.json()["user_error"]["code"] == code, resp.text


@pytest.mark.asyncio
async def test_line_amount_cannot_go_negative():
    # No hyphen: terminal_id is "{tenant}-{store}-{no}" and is split on "-".
    tenant_id = "LAG" + uuid.uuid4().hex[:8].upper()
    store_code = "5002"
    terminal_no = 1
    item_code = "LAGITEM"

    headers = {"Authorization": f"Bearer {_admin_token(tenant_id)}"}

    _post("URL_TERMINAL", "/api/v1/tenants", headers, json={
        "tenant_id": tenant_id, "tenant_name": "Line Amount Tenant",
        "stores": [], "tags": ["e2e-line-amount-guards"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/staff", headers, json={
        "id": "S001", "name": "Line Staff", "pin": "1234", "roles": ["staff"],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/categories", headers, json={
        "categoryCode": "001", "description": "Default Category",
        "descriptionShort": "DC", "taxCode": "01",
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/items", headers, json={
        "itemCode": item_code, "description": "Line Item",
        "unitPrice": 689.0, "unitCost": 50.0,
        "taxCode": "01", "categoryCode": "001",
        "itemDetails": [], "imageUrls": [],
    })
    _post("URL_MASTER_DATA", f"/api/v1/tenants/{tenant_id}/payments", headers, json={
        "paymentCode": "01", "description": "Cash",
        "limitAmount": 0.0, "canRefund": True,
        "canDepositOver": True, "canChange": True, "isActive": True,
    })
    _post("URL_TERMINAL", f"/api/v1/tenants/{tenant_id}/stores", headers, json={
        "store_code": store_code, "store_name": "Line Store", "tags": [],
    })

    with _client("URL_TERMINAL") as c:
        resp = c.post(
            "/api/v1/terminals",
            json={"store_code": store_code, "terminal_no": terminal_no, "description": "Line Terminal"},
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
    q = f"?terminal_id={terminal_id}"
    with _client("URL_CART") as c:
        resp = c.post(
            f"/api/v1/carts{q}",
            json={
                "tenant_id": tenant_id, "terminal_id": terminal_id,
                "operator_code": "S001", "operator_name": "Line Staff",
            },
            headers=key_headers,
        )
        assert resp.status_code == 201, resp.text
        cart_id = resp.json()["data"]["cartId"]
        base = f"/api/v1/carts/{cart_id}"

        for quantity in (0, -1):
            resp = c.post(f"{base}/lineItems{q}", json=[{"itemCode": item_code, "quantity": quantity}], headers=key_headers)
            _assert_refused(resp, "402007")
        resp = c.post(
            f"{base}/lineItems{q}", json=[{"itemCode": item_code, "quantity": 1, "unitPrice": -689.0}], headers=key_headers
        )
        _assert_refused(resp, "402008")

        resp = c.post(f"{base}/lineItems{q}", json=[{"itemCode": item_code, "quantity": 2}], headers=key_headers)
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]["lineItems"]) == 1, resp.text

        resp = c.post(
            f"{base}/lineItems/1/discounts{q}",
            json=[{"discountType": "DiscountAmount", "discountValue": -500.0}],
            headers=key_headers,
        )
        _assert_refused(resp, "402009")

        # Accepted: 1,378 >= 1,000.
        resp = c.post(
            f"{base}/lineItems/1/discounts{q}",
            json=[{"discountType": "DiscountAmount", "discountValue": 1000.0}],
            headers=key_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["lineItems"][0]["amount"] == 378.0, resp.text

        resp = c.patch(f"{base}/lineItems/1/quantity{q}", json={"quantity": 1}, headers=key_headers)
        _assert_refused(resp, "402002")
        resp = c.patch(f"{base}/lineItems/1/quantity{q}", json={"quantity": 0}, headers=key_headers)
        _assert_refused(resp, "402007")
        resp = c.patch(f"{base}/lineItems/1/unitPrice{q}", json={"unitPrice": 400.0}, headers=key_headers)
        _assert_refused(resp, "402002")
        resp = c.patch(f"{base}/lineItems/1/unitPrice{q}", json={"unitPrice": -1.0}, headers=key_headers)
        _assert_refused(resp, "402008")

        # Every refusal left the line as it was, and the cart still settles.
        resp = c.post(f"{base}/subtotal{q}", headers=key_headers)
        assert resp.status_code == 200, resp.text
        line = resp.json()["data"]["lineItems"][0]
        assert (line["quantity"], line["unitPrice"], line["amount"]) == (2, 689.0, 378.0), resp.text
        balance = resp.json()["data"]["balanceAmount"]

        resp = c.post(
            f"{base}/payments{q}", json=[{"paymentCode": "01", "amount": balance}], headers=key_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["balanceAmount"] == 0, resp.text

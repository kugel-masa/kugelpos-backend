# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Integration coverage for cart operations not exercised elsewhere.

Covers the 17 endpoints that test_setup_data / test_payment_cashless_error
don't reach:

  POST   /tenants
  POST   /carts/{cart_id}/cancel
  POST   /carts/{cart_id}/discounts
  POST   /carts/{cart_id}/lineItems/{lineNo}/cancel
  POST   /carts/{cart_id}/lineItems/{lineNo}/discounts
  PATCH  /carts/{cart_id}/lineItems/{lineNo}/quantity
  PATCH  /carts/{cart_id}/lineItems/{lineNo}/unitPrice
  POST   /carts/{cart_id}/subtotal
  POST   /carts/{cart_id}/bill
  POST   /carts/{cart_id}/resume-item-entry
  GET    /tenants/{tid}/stores/{sc}/terminals/{tn}/transactions
  GET    /tenants/{tid}/stores/{sc}/terminals/{tn}/transactions/{tno}
  POST   /tenants/{tid}/stores/{sc}/terminals/{tn}/transactions/{tno}/void
  POST   /tenants/{tid}/stores/{sc}/terminals/{tn}/transactions/{tno}/return
  POST   /tenants/{tid}/stores/{sc}/terminals/{tn}/transactions/{tno}/delivery-status

Cart drives the in-process FastAPI app via ASGITransport. All outbound
HTTP / gRPC is mocked by the conftest's `mock_outbound` and
`mock_grpc_item_lookup` fixtures.
"""
import os
from datetime import datetime

import pytest
from fastapi import status


# ---------------------------------------------------------------------------
# Cart-creation helpers
# ---------------------------------------------------------------------------


async def _create_cart(http_client, headers, terminal_id, user_id="9999"):
    """Create a fresh cart and return its cart_id."""
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={
            "tenant_id": os.environ.get("TENANT_ID"),
            "terminal_id": terminal_id,
            "operator_code": user_id,
            "operator_name": "Test Operator",
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["cartId"]


async def _add_item(http_client, headers, terminal_id, cart_id, item_code="49-01", quantity=1):
    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": item_code, "quantity": quantity}],
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


def _api_headers():
    return {
        "X-API-KEY": "test-api-key-12345",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tenants(http_client, admin_header):
    """POST /tenants creates per-tenant DB on cart's side. Idempotent."""
    tenant_id = os.environ.get("TENANT_ID")
    response = await http_client.post(
        "/api/v1/tenants",
        json={"tenant_id": tenant_id},
        headers=admin_header,
    )
    assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST), (
        response.text
    )


@pytest.mark.asyncio
async def test_cancel_cart(http_client):
    """POST /carts/{cart_id}/cancel cancels the cart after items have been added."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/cancel?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_apply_cart_discount(http_client):
    """POST /carts/{cart_id}/discounts after subtotal applies a flat-amount
    discount and returns 200."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 50}],
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_cancel_lineitem(http_client):
    """POST /carts/{cart_id}/lineItems/{lineNo}/cancel cancels a single line item."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/1/cancel?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_apply_lineitem_discount(http_client):
    """POST /carts/{cart_id}/lineItems/{lineNo}/discounts applies a per-line
    discount and returns 200."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems/1/discounts?terminal_id={terminal_id}",
        json=[{"discountType": "DiscountAmount", "discountValue": 10}],
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_update_lineitem_quantity(http_client):
    """PATCH /carts/{cart_id}/lineItems/{lineNo}/quantity updates the qty."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id, quantity=1)

    response = await http_client.patch(
        f"/api/v1/carts/{cart_id}/lineItems/1/quantity?terminal_id={terminal_id}",
        json={"quantity": 5},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["lineItems"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_update_lineitem_unitprice(http_client):
    """PATCH /carts/{cart_id}/lineItems/{lineNo}/unitPrice overrides the unit price."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.patch(
        f"/api/v1/carts/{cart_id}/lineItems/1/unitPrice?terminal_id={terminal_id}",
        json={"unitPrice": 200},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["lineItems"][0]["unitPrice"] == 200


@pytest.mark.asyncio
async def test_subtotal(http_client):
    """POST /carts/{cart_id}/subtotal moves the cart into `paying` state."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_bill_full_payment(http_client):
    """Full payment + bill happy path: subtotal -> exact-amount cash
    payment -> bill commits the transaction."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    balance = response.json()["data"].get("balanceAmount") or 100

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": balance}],
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_resume_item_entry(http_client):
    """POST /carts/{cart_id}/resume-item-entry transitions paying state back to entering_item."""
    terminal_id = f"{os.environ.get('TENANT_ID')}-5678-9"
    headers = _api_headers()
    cart_id = await _create_cart(http_client, headers, terminal_id)
    await _add_item(http_client, headers, terminal_id, cart_id)

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/resume-item-entry?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_get_transactions_list(http_client):
    """GET /tenants/.../transactions returns a (possibly empty) tranlog list.

    Uses X-API-KEY auth (the documented path for tranlog query); the
    conftest's terminal-lookup respx mock provides the terminal_info.
    """
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions"
        f"?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_get_transaction_detail_404(http_client):
    """GET /transactions/{tno} for a nonexistent transaction returns 404."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/999999"
        f"?terminal_id={terminal_id}",
        headers=headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_void_transaction_404(http_client):
    """POST .../transactions/{tno}/void on a missing tranlog returns 404."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/999999/void"
        f"?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 0}],
        headers=headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_return_transaction_404(http_client):
    """POST .../transactions/{tno}/return on a missing tranlog returns 404."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no}"
    headers = _api_headers()

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/999999/return"
        f"?terminal_id={terminal_id}",
        json=[{"paymentCode": "01", "amount": 0}],
        headers=headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_delivery_status_requires_pubsub_auth(http_client, admin_header):
    """POST .../transactions/{tno}/delivery-status is for Dapr pub/sub —
    a regular admin token is rejected with 401."""
    tenant_id = os.environ.get("TENANT_ID")
    store_code = os.environ.get("STORE_CODE", "5678")
    terminal_no = 9

    response = await http_client.post(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions/1/delivery-status",
        json={
            "event_id": "evt-int-001",
            "service": "report",
            "status": "delivered",
            "message": "ok",
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

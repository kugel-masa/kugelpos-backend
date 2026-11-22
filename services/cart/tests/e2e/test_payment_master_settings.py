# Copyright 2026 masa@kugel
"""cart applies the payment master's limit and refund settings (issue #309).

The master-data setup gives cashless (11) a limit of 100000 and can_refund=false;
cash (01) has no limit and is refundable.
"""
import os

import pytest
from fastapi import status
from httpx import AsyncClient

# These tests drive the cart without carrying its snapshot (issue #156).
pytestmark = pytest.mark.dual_only

CASHLESS_LIMIT = 100000


def _terminal():
    terminal_id = os.environ.get("TERMINAL_ID")
    parts = terminal_id.split("-")
    return terminal_id, os.environ.get("TENANT_ID"), parts[1], int(parts[2])


def _header():
    return {"X-API-KEY": os.environ.get("API_KEY")}


async def _cart_in_payment(http_client: AsyncClient, quantity: int) -> tuple[str, float]:
    terminal_id = _terminal()[0]
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"transaction_type": 101, "user_id": "99", "user_name": "John Doe"},
        headers=_header(),
    )
    assert response.status_code == status.HTTP_201_CREATED
    cart_id = response.json()["data"]["cartId"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json=[{"itemCode": "49-01", "quantity": quantity}],
        headers=_header(),
    )
    assert response.status_code == status.HTTP_200_OK

    response = await http_client.post(f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}", headers=_header())
    assert response.status_code == status.HTTP_200_OK
    return cart_id, response.json()["data"]["balanceAmount"]


async def _pay(http_client: AsyncClient, cart_id: str, payment_code: str, amount: float):
    return await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={_terminal()[0]}",
        json=[{"paymentCode": payment_code, "amount": amount, "detail": None}],
        headers=_header(),
    )


def _error_code(response) -> str:
    return response.json().get("userError", {}).get("code")


@pytest.mark.asyncio
async def test_a_payment_over_the_limit_of_its_method_is_refused(http_client: AsyncClient):
    cart_id, balance = await _cart_in_payment(http_client, quantity=2000)
    assert balance > CASHLESS_LIMIT, "the cart has to be worth more than the limit"

    # Split under the limit, then one yen past it
    response = await _pay(http_client, cart_id, "11", CASHLESS_LIMIT - 1)
    assert response.status_code == status.HTTP_200_OK
    response = await _pay(http_client, cart_id, "11", 2)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert _error_code(response) == "403017"

    # The refused payment left the cart as it was; the rest can be paid in cash
    response = await _pay(http_client, cart_id, "01", balance - (CASHLESS_LIMIT - 1))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["balanceAmount"] == 0


@pytest.mark.asyncio
async def test_a_return_by_a_method_that_cannot_refund_is_refused(http_client: AsyncClient):
    terminal_id, tenant_id, store_code, terminal_no = _terminal()
    cart_id, balance = await _cart_in_payment(http_client, quantity=1)
    assert (await _pay(http_client, cart_id, "01", balance)).status_code == status.HTTP_200_OK
    response = await http_client.post(f"/api/v1/carts/{cart_id}/bill?terminal_id={terminal_id}", headers=_header())
    assert response.status_code == status.HTTP_200_OK
    transaction_no = response.json()["data"]["transactionNo"]
    url = (
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}"
        f"/transactions/{transaction_no}/return?terminal_id={terminal_id}"
    )

    response = await http_client.post(
        url, json=[{"paymentCode": "11", "amount": balance, "detail": None}], headers=_header()
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert _error_code(response) == "403014"

    # The refusal did not mark the sale as returned: a cash refund goes through
    response = await http_client.post(
        url, json=[{"paymentCode": "01", "amount": balance, "detail": None}], headers=_header()
    )
    assert response.status_code == status.HTTP_200_OK

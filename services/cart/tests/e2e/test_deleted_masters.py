# Copyright 2026 masa@kugel
"""cart does not use a logically deleted master record (issue #324).

master-data's default reads skip deleted records, so once cart's cache is
invalidated a deleted item cannot be sold, a deleted payment method cannot pay
and a deleted promotion gives no discount. cart's own code does not change.

Driven on the carried path (the snapshot travels with every request). A
deleted setting is checked at master-data (its value read answers 404, the
same as a missing setting, which cart already treats as "use the default").
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID")


def _store_code() -> str:
    return os.environ.get("TERMINAL_ID").split("-")[1]


def _api_header() -> dict:
    return {"X-API-KEY": os.environ.get("API_KEY")}


def _master_data() -> str:
    return f"{os.environ.get('BASE_URL_MASTER_DATA')}/tenants/{_tenant_id()}"


@pytest_asyncio.fixture
async def admin(http_client):
    from tests.e2e.test_cart import create_tenant, get_authentication_token

    token = await get_authentication_token()
    await create_tenant(http_client, token)
    return {"Authorization": f"Bearer {token}"}


async def _invalidate(http_client: AsyncClient, admin: dict, namespace: str):
    params = {"namespace": namespace}
    if namespace in ("item_master", "promotion_master"):
        params["store_code"] = _store_code()
    response = await http_client.delete("/api/v1/cache/master-data", params=params, headers=admin)
    assert response.status_code == status.HTTP_200_OK, response.text


async def _new_cart(http_client: AsyncClient, terminal_id: str) -> tuple[str, str]:
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"carrySnapshot": True, "transaction_type": 101, "user_id": "99", "user_name": "Deleted masters"},
        headers=_api_header(),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    return data["cartId"], data["signedSnapshot"]


async def _add(http_client, terminal_id, cart_id, snapshot, item_code):
    return await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": item_code, "quantity": 1}]},
        headers=_api_header(),
    )


async def _create_item(admin: dict, code: str, category: str = "001"):
    async with AsyncClient() as client:
        response = await client.post(
            f"{_master_data()}/items",
            json={"itemCode": code, "description": f"Deletable {code}", "unitPrice": 300, "unitCost": 100,
                  "itemDetails": [], "imageUrls": [], "categoryCode": category, "taxCode": "01"},
            headers=admin,
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        response = await client.post(
            f"{_master_data()}/stores/{_store_code()}/items", json={"itemCode": code, "storePrice": 300.0}, headers=admin
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text


async def _delete(admin: dict, path: str):
    async with AsyncClient() as client:
        response = await client.delete(f"{_master_data()}{path}", headers=admin)
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_a_deleted_item_cannot_be_sold(http_client, opened_terminal_id, admin):
    code = f"DEL{uuid.uuid4().hex[:6].upper()}"
    await _create_item(admin, code)
    await _invalidate(http_client, admin, "item_master")
    cart_id, snapshot = await _new_cart(http_client, opened_terminal_id)
    response = await _add(http_client, opened_terminal_id, cart_id, snapshot, code)
    assert response.status_code == status.HTTP_200_OK, response.text

    await _delete(admin, f"/items/{code}")
    await _invalidate(http_client, admin, "item_master")

    cart_id, snapshot = await _new_cart(http_client, opened_terminal_id)
    response = await _add(http_client, opened_terminal_id, cart_id, snapshot, code)
    assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY), response.text


@pytest.mark.asyncio
async def test_a_deleted_payment_method_cannot_pay(http_client, opened_terminal_id, admin):
    others = "12"
    async with AsyncClient() as client:
        response = await client.get(f"{_master_data()}/payments/{others}", headers=admin)
    assert response.status_code == status.HTTP_200_OK, response.text
    saved = response.json()["data"]

    await _delete(admin, f"/payments/{others}")
    try:
        await _invalidate(http_client, admin, "payment_master")
        cart_id, snapshot = await _new_cart(http_client, opened_terminal_id)
        response = await _add(http_client, opened_terminal_id, cart_id, snapshot, "49-01")
        assert response.status_code == status.HTTP_200_OK, response.text
        snapshot = response.json()["data"]["signedSnapshot"]
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/subtotal?terminal_id={opened_terminal_id}",
            json={"signedSnapshot": snapshot, "payload": {}},
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        snapshot = response.json()["data"]["signedSnapshot"]

        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/payments?terminal_id={opened_terminal_id}",
            json={"signedSnapshot": snapshot, "payload": [{"paymentCode": others, "amount": 1}]},
            headers=_api_header(),
        )
        # Refused as a client error (an unknown payment method), never a 500
        assert 400 <= response.status_code < 500, response.text
    finally:
        # Creating the code again restores it (issue #324)
        async with AsyncClient() as client:
            restored = await client.post(
                f"{_master_data()}/payments",
                json={key: saved[key] for key in ("paymentCode", "description", "limitAmount", "canRefund",
                                                   "canDepositOver", "canChange", "isActive")},
                headers=admin,
            )
        assert restored.status_code == status.HTTP_201_CREATED, restored.text
        await _invalidate(http_client, admin, "payment_master")


@pytest.mark.asyncio
async def test_a_deleted_promotion_gives_no_discount(http_client, opened_terminal_id, admin):
    category = f"DC{uuid.uuid4().hex[:4].upper()}"
    item = f"DEL{uuid.uuid4().hex[:6].upper()}"
    promo = f"DELP{uuid.uuid4().hex[:6].upper()}"
    async with AsyncClient() as client:
        response = await client.post(
            f"{_master_data()}/categories",
            json={"categoryCode": category, "description": "Deletable", "descriptionShort": "Del", "taxCode": "01"},
            headers=admin,
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
    await _create_item(admin, item, category)
    now = datetime.now()
    async with AsyncClient() as client:
        response = await client.post(
            f"{_master_data()}/promotions",
            json={"promotionCode": promo, "promotionType": "category_discount", "name": promo, "description": promo,
                  "startDatetime": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
                  "endDatetime": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
                  "isActive": True,
                  "detail": {"targetStoreCodes": [_store_code()], "targetCategoryCodes": [category], "discountRate": 10.0}},
            headers=admin,
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
    await _invalidate(http_client, admin, "item_master")
    await _invalidate(http_client, admin, "promotion_master")

    def promo_codes(response):
        line = response.json()["data"]["lineItems"][-1]
        return [d.get("promotionCode") for d in line.get("discounts", [])]

    cart_id, snapshot = await _new_cart(http_client, opened_terminal_id)
    response = await _add(http_client, opened_terminal_id, cart_id, snapshot, item)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert promo in promo_codes(response)

    await _delete(admin, f"/promotions/{promo}")
    await _invalidate(http_client, admin, "promotion_master")

    cart_id, snapshot = await _new_cart(http_client, opened_terminal_id)
    response = await _add(http_client, opened_terminal_id, cart_id, snapshot, item)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert promo not in promo_codes(response)


@pytest.mark.asyncio
async def test_a_deleted_setting_reads_as_missing(admin):
    name = f"DELSET{uuid.uuid4().hex[:6].upper()}"
    async with AsyncClient() as client:
        response = await client.post(
            f"{_master_data()}/settings", json={"name": name, "defaultValue": "x", "values": []}, headers=admin
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
    await _delete(admin, f"/settings/{name}")

    async with AsyncClient() as client:
        response = await client.get(
            f"{_master_data()}/settings/{name}/value", params={"store_code": _store_code(), "terminal_no": 1}, headers=admin
        )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

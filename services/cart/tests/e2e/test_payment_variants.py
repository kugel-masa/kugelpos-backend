# Copyright 2026 masa@kugel
"""cart records a payment's variant (sub-code), and voids and returns follow the sale's tenders (issue #311).

The e2e tenant is shared with the rest of the cart suite and a variant cannot be
deleted, so these tests:

- register variants under Others (12) with codes unique to the run, never under
  the methods other tests pay with without a variant;
- invalidate cart's payment-master cache after every master change (its TTL is
  600 s), with the tenant admin's token;
- stop every variant they registered, and put Others' settings back, when they
  finish, failures included.

Sales are driven on the carried path (the snapshot travels with every request).
Voids and returns are run against sales staged in the cart database, the way
test_void_return_scope.py stages them.
"""

import os
import random
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient

from app.config.settings import settings

OTHERS = "12"
OTHERS_SETTINGS = {
    "description": "Others",
    "limitAmount": 100000.0,
    "canRefund": False,
    "canDepositOver": False,
    "canChange": False,
    "isActive": True,
}


def _tenant_id() -> str:
    return os.environ.get("TENANT_ID")


def _api_header() -> dict:
    return {"X-API-KEY": os.environ.get("API_KEY")}


def _error_code(response) -> str:
    return response.json().get("userError", {}).get("code")


async def _admin_header() -> dict:
    from tests.e2e.test_cart import get_authentication_token

    return {"Authorization": f"Bearer {await get_authentication_token()}"}


class MasterData:
    """Variants and settings of Others, changed through master-data, and cart told of each change."""

    def __init__(self, http_client: AsyncClient, admin_header: dict):
        self.cart = http_client
        self.admin = admin_header
        self.base = f"{os.environ.get('BASE_URL_MASTER_DATA')}/tenants/{_tenant_id()}/payments"
        self.suffix = uuid.uuid4().hex[:6].upper()
        self.registered: list[str] = []

    def code(self, name: str) -> str:
        return f"{name}{self.suffix}"

    async def _invalidate(self):
        response = await self.cart.delete(
            "/api/v1/cache/master-data", params={"namespace": "payment_master"}, headers=self.admin
        )
        assert response.status_code == status.HTTP_200_OK, response.text

    async def add(self, name: str, display: str, payment_code: str = OTHERS) -> str:
        code = self.code(name)
        async with AsyncClient() as client:
            response = await client.post(
                f"{self.base}/{payment_code}/variants",
                json={"variantCode": code, "name": display},
                headers=self.admin,
            )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        self.registered.append((payment_code, code, display))
        await self._invalidate()
        return code

    async def set_variant(self, code: str, display: str, is_active: bool, payment_code: str = OTHERS):
        async with AsyncClient() as client:
            response = await client.put(
                f"{self.base}/{payment_code}/variants/{code}",
                json={"name": display, "isActive": is_active},
                headers=self.admin,
            )
        assert response.status_code == status.HTTP_200_OK, response.text
        await self._invalidate()

    async def set_others(self, **overrides):
        async with AsyncClient() as client:
            response = await client.put(
                f"{self.base}/{OTHERS}", json={**OTHERS_SETTINGS, **overrides}, headers=self.admin
            )
        assert response.status_code == status.HTTP_200_OK, response.text
        await self._invalidate()

    async def restore(self):
        async with AsyncClient() as client:
            for payment_code, code, display in self.registered:
                await client.put(
                    f"{self.base}/{payment_code}/variants/{code}",
                    json={"name": display, "isActive": False},
                    headers=self.admin,
                )
            await client.put(f"{self.base}/{OTHERS}", json=OTHERS_SETTINGS, headers=self.admin)
        await self._invalidate()


@pytest_asyncio.fixture
async def master(http_client):
    from tests.e2e.test_cart import create_tenant, get_authentication_token

    await create_tenant(http_client, await get_authentication_token())
    md = MasterData(http_client, await _admin_header())
    try:
        yield md
    finally:
        await md.restore()


# ---------------------------------------------------------------------------
# A sale, on the carried path
# ---------------------------------------------------------------------------


async def _cart_in_payment(http_client: AsyncClient, terminal_id: str) -> tuple[str, dict, float]:
    response = await http_client.post(
        f"/api/v1/carts?terminal_id={terminal_id}",
        json={"carrySnapshot": True, "transaction_type": 101, "user_id": "99", "user_name": "Variants"},
        headers=_api_header(),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    cart_id, snapshot = data["cartId"], data["signedSnapshot"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/lineItems?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": [{"itemCode": "49-01", "quantity": 2}]},
        headers=_api_header(),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    snapshot = response.json()["data"]["signedSnapshot"]

    response = await http_client.post(
        f"/api/v1/carts/{cart_id}/subtotal?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": {}},
        headers=_api_header(),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    return cart_id, data["signedSnapshot"], data["balanceAmount"]


async def _pay(http_client, terminal_id, cart_id, snapshot, payments: list[dict]):
    return await http_client.post(
        f"/api/v1/carts/{cart_id}/payments?terminal_id={terminal_id}",
        json={"signedSnapshot": snapshot, "payload": payments},
        headers=_api_header(),
    )


@pytest.mark.asyncio
async def test_a_payment_records_the_variant_it_names(http_client, opened_terminal_id, master):
    visa = await master.add("VISA", "VISA")
    paypay = await master.add("PAYPAY", "PayPay")
    cart_id, snapshot, balance = await _cart_in_payment(http_client, opened_terminal_id)

    response = await _pay(
        http_client, opened_terminal_id, cart_id, snapshot, [{"paymentCode": OTHERS, "amount": 1, "variantCode": paypay}]
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    line = response.json()["data"]["payments"][-1]
    assert (line["paymentCode"], line["variantCode"], line["paymentName"], line["builtinPaymentName"]) == (
        OTHERS,
        paypay,
        "PayPay",
        "Others",
    )
    assert visa != paypay


@pytest.mark.asyncio
async def test_a_wrong_or_missing_variant_is_refused(http_client, opened_terminal_id, master):
    await master.add("VISA", "VISA")
    await master.add("PAYPAY", "PayPay")
    stopped = await master.add("AMEX", "AMEX")
    await master.set_variant(stopped, "AMEX", is_active=False)
    cart_id, snapshot, _ = await _cart_in_payment(http_client, opened_terminal_id)

    cases = [
        ({"paymentCode": OTHERS, "amount": 1}, "403020"),  # two active variants, none named
        ({"paymentCode": OTHERS, "amount": 1, "variantCode": master.code("JCB")}, "403018"),  # unknown
        ({"paymentCode": "11", "amount": 1, "variantCode": master.code("VISA")}, "403018"),  # another method's
        ({"paymentCode": OTHERS, "amount": 1, "variantCode": stopped}, "403019"),  # stopped
    ]
    for payment, code in cases:
        response = await _pay(http_client, opened_terminal_id, cart_id, snapshot, [payment])
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (payment, response.text)
        assert _error_code(response) == code, (payment, response.text)


@pytest.mark.asyncio
async def test_a_single_active_variant_is_taken_when_none_is_named(http_client, opened_terminal_id, master):
    only = await master.add("GIFT", "Gift card")
    cart_id, snapshot, _ = await _cart_in_payment(http_client, opened_terminal_id)

    response = await _pay(http_client, opened_terminal_id, cart_id, snapshot, [{"paymentCode": OTHERS, "amount": 1}])

    assert response.status_code == status.HTTP_200_OK, response.text
    line = response.json()["data"]["payments"][-1]
    assert (line["variantCode"], line["paymentName"]) == (only, "Gift card")


@pytest.mark.asyncio
async def test_a_method_without_variants_records_as_before(http_client, opened_terminal_id, master):
    cart_id, snapshot, balance = await _cart_in_payment(http_client, opened_terminal_id)

    response = await _pay(
        http_client, opened_terminal_id, cart_id, snapshot, [{"paymentCode": "01", "amount": int(balance)}]
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    line = response.json()["data"]["payments"][-1]
    assert (line["variantCode"], line["paymentName"], line["builtinPaymentName"]) == (None, "Cash", "Cash")


@pytest.mark.asyncio
async def test_a_refused_second_payment_records_neither(http_client, opened_terminal_id, master):
    visa = await master.add("VISA", "VISA")
    await master.add("PAYPAY", "PayPay")
    cart_id, snapshot, balance = await _cart_in_payment(http_client, opened_terminal_id)

    response = await _pay(
        http_client,
        opened_terminal_id,
        cart_id,
        snapshot,
        [
            {"paymentCode": OTHERS, "amount": 1, "variantCode": visa},
            {"paymentCode": OTHERS, "amount": 1, "variantCode": master.code("JCB")},
        ],
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert _error_code(response) == "403018"

    # The snapshot the client still holds is the cart as it was: nothing was paid
    response = await _pay(
        http_client, opened_terminal_id, cart_id, snapshot, [{"paymentCode": OTHERS, "amount": 1, "variantCode": visa}]
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert len(data["payments"]) == 1
    assert data["balanceAmount"] == balance - 1


@pytest.mark.asyncio
async def test_a_line_keeps_its_variant_when_the_variant_is_stopped_before_the_bill(
    http_client, opened_terminal_id, master
):
    visa = await master.add("VISA", "VISA")
    paypay = await master.add("PAYPAY", "PayPay")
    cart_id, snapshot, balance = await _cart_in_payment(http_client, opened_terminal_id)
    response = await _pay(
        http_client, opened_terminal_id, cart_id, snapshot, [{"paymentCode": OTHERS, "amount": 1, "variantCode": visa}]
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    snapshot = response.json()["data"]["signedSnapshot"]

    await master.set_variant(visa, "VISA renamed", is_active=False)

    response = await _pay(
        http_client,
        opened_terminal_id,
        cart_id,
        snapshot,
        [{"paymentCode": OTHERS, "amount": int(balance) - 1, "variantCode": paypay}],
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert [(p["variantCode"], p["paymentName"]) for p in data["payments"]] == [(visa, "VISA"), (paypay, "PayPay")]

    seq = 8_000_000 + random.randint(0, 999_999)
    try:
        response = await http_client.post(
            f"/api/v1/carts/{cart_id}/bill?terminal_id={opened_terminal_id}",
            json={
                "signedSnapshot": data["signedSnapshot"],
                "payload": {
                    "seq": seq,
                    "receiptCounter": 1,
                    "transactionDatetime": datetime.now().replace(microsecond=0).isoformat(),
                },
            },
            headers=_api_header(),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        billed = response.json()["data"]["payments"]
        assert [(p["variantCode"], p["paymentName"]) for p in billed] == [(visa, "VISA"), (paypay, "PayPay")]
    finally:
        db = await _cart_db()
        await db[settings.DB_COLLECTION_NAME_TRAN_LOG].delete_many({"cart_id": cart_id})


# ---------------------------------------------------------------------------
# Voids and returns, against a staged sale of 12/VISA 1000 and 12/PAYPAY 2000
# ---------------------------------------------------------------------------


async def _cart_db():
    from kugel_common.database import database as db_helper

    return await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{_tenant_id()}")


async def _terminal_state():
    async with AsyncClient(base_url=os.environ.get("BASE_URL_TERMINAL")) as client:
        response = await client.get(f"/terminals/{os.environ.get('TERMINAL_ID')}", headers=_api_header())
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    return data["businessDate"], data["businessCounter"]


class StagedSale:
    """A completed sale in this terminal's current session, paid by two variants of Others."""

    def __init__(self, visa: str, paypay: str):
        self.visa, self.paypay = visa, paypay
        self.store_code = os.environ.get("STORE_CODE")
        self.terminal_no = int(os.environ.get("TERMINAL_ID").split("-")[-1])
        self.transaction_no = 7_300_000 + random.randint(0, 99_999)
        self.cart_id = f"e2e-variants-{uuid.uuid4().hex[:8]}"

    async def insert(self):
        business_date, business_counter = await _terminal_state()
        self.business_counter = business_counter
        db = await _cart_db()
        await db[settings.DB_COLLECTION_NAME_TRAN_LOG].insert_one(
            {
                "tenant_id": _tenant_id(),
                "store_code": self.store_code,
                "store_name": f"Store {self.store_code}",
                "terminal_no": self.terminal_no,
                "business_date": business_date,
                "business_counter": business_counter,
                "open_counter": 1,
                "transaction_no": self.transaction_no,
                "transaction_type": 101,
                "receipt_no": self.transaction_no,
                "generate_date_time": "2026-01-01T10:00:00",
                "cart_id": self.cart_id,
                "staff": {"id": "S001", "name": "Staff1"},
                "line_items": [],
                "payments": [
                    {
                        "payment_no": 1,
                        "payment_code": OTHERS,
                        "description": "VISA",
                        "variant_code": self.visa,
                        "builtin_description": "Others",
                        "amount": 1000.0,
                        "deposit_amount": 0.0,
                    },
                    {
                        "payment_no": 2,
                        "payment_code": OTHERS,
                        "description": "PayPay",
                        "variant_code": self.paypay,
                        "builtin_description": "Others",
                        "amount": 2000.0,
                        "deposit_amount": 0.0,
                    },
                ],
                "taxes": [],
                "subtotal_discounts": [],
                "sales": {"total_amount_with_tax": 3000.0, "total_amount": 3000.0},
            }
        )
        return self

    def url(self, action: str) -> str:
        return (
            f"/api/v1/tenants/{_tenant_id()}/stores/{self.store_code}/terminals/{self.terminal_no}"
            f"/transactions/{self.transaction_no}/{action}?terminal_id={os.environ.get('TERMINAL_ID')}"
            f"&business_counter={self.business_counter}"
        )

    async def cleanup(self):
        db = await _cart_db()
        tranlogs = db[settings.DB_COLLECTION_NAME_TRAN_LOG]
        await tranlogs.delete_many({"cart_id": self.cart_id})
        await tranlogs.delete_many(
            {"origin.transaction_no": self.transaction_no, "origin.store_code": self.store_code}
        )
        await db[settings.DB_COLLECTION_NAME_STATUS_TRAN].delete_many(
            {"store_code": self.store_code, "transaction_no": self.transaction_no}
        )


@pytest_asyncio.fixture
async def sale(master, opened_terminal_id):
    visa = await master.add("VISA", "VISA")
    paypay = await master.add("PAYPAY", "PayPay")
    staged = await StagedSale(visa, paypay).insert()
    try:
        yield staged
    finally:
        await staged.cleanup()


def _tender(code, amount, variant=None):
    payment = {"paymentCode": code, "amount": amount}
    if variant is not None:
        payment["variantCode"] = variant
    return payment


@pytest.mark.asyncio
async def test_a_void_names_each_tender_of_the_sale(http_client, sale):
    response = await http_client.post(
        sale.url("void"),
        json=[_tender(OTHERS, 1000, sale.visa), _tender(OTHERS, 2000, sale.paypay)],
        headers=_api_header(),
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    lines = response.json()["data"]["payments"]
    assert [(p["variantCode"], p["paymentName"], p["builtinPaymentName"]) for p in lines] == [
        (sale.visa, "VISA", "Others"),
        (sale.paypay, "PayPay", "Others"),
    ]


@pytest.mark.asyncio
async def test_a_void_other_than_the_sale_is_refused(http_client, master, sale):
    cases = [
        [_tender(OTHERS, 3000)],  # variant left out: the sale has no 12 without a variant
        [_tender(OTHERS, 3000, sale.visa)],  # not what the sale took by VISA
        [_tender(OTHERS, 1000, master.code("JCB")), _tender(OTHERS, 2000, sale.paypay)],  # not a tender of the sale
        [_tender("01", 3000)],  # cash was not a tender of the sale
    ]
    for payments in cases:
        response = await http_client.post(sale.url("void"), json=payments, headers=_api_header())
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (payments, response.text)


@pytest.mark.asyncio
async def test_a_void_of_a_variant_stopped_and_renamed_since_the_sale_is_taken(http_client, master, sale):
    await master.set_variant(sale.paypay, "PayPay renamed", is_active=False)

    response = await http_client.post(
        sale.url("void"),
        json=[_tender(OTHERS, 1000, sale.visa), _tender(OTHERS, 2000, sale.paypay)],
        headers=_api_header(),
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["payments"][1]["paymentName"] == "PayPay"


@pytest.mark.asyncio
async def test_a_return_to_a_tender_of_the_sale_and_cash(http_client, master, sale):
    await master.set_others(canRefund=True)

    response = await http_client.post(
        sale.url("return"), json=[_tender(OTHERS, 2000, sale.paypay), _tender("01", 1000)], headers=_api_header()
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    lines = response.json()["data"]["payments"]
    assert [(p["paymentCode"], p["variantCode"], p["paymentName"]) for p in lines] == [
        (OTHERS, sale.paypay, "PayPay"),
        ("01", None, "Cash"),
    ]


@pytest.mark.asyncio
async def test_a_return_all_in_cash(http_client, sale):
    response = await http_client.post(sale.url("return"), json=[_tender("01", 3000)], headers=_api_header())

    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_a_return_to_a_variant_stopped_since_the_sale(http_client, master, sale):
    await master.set_others(canRefund=True)
    await master.set_variant(sale.paypay, "PayPay renamed", is_active=False)

    response = await http_client.post(
        sale.url("return"), json=[_tender(OTHERS, 2000, sale.paypay), _tender("01", 1000)], headers=_api_header()
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["data"]["payments"][0]["paymentName"] == "PayPay"


@pytest.mark.asyncio
async def test_a_return_beyond_the_sale_is_refused(http_client, master, sale):
    await master.set_others(canRefund=True)

    cases = [
        ([_tender(OTHERS, 3000, sale.visa)], "403022"),  # more than the sale took by VISA
        ([_tender(OTHERS, 1000, master.code("JCB")), _tender("01", 2000)], "403021"),  # not a tender of the sale
        ([_tender("11", 3000)], "403021"),  # a method the sale did not use
    ]
    for payments, code in cases:
        response = await http_client.post(sale.url("return"), json=payments, headers=_api_header())
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (payments, response.text)
        assert _error_code(response) == code, (payments, response.text)


@pytest.mark.asyncio
async def test_a_return_to_a_method_that_cannot_refund_is_refused_but_cash_is_taken(http_client, sale):
    response = await http_client.post(
        sale.url("return"), json=[_tender(OTHERS, 2000, sale.paypay), _tender("01", 1000)], headers=_api_header()
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert _error_code(response) == "403014"

    response = await http_client.post(sale.url("return"), json=[_tender("01", 3000)], headers=_api_header())
    assert response.status_code == status.HTTP_200_OK, response.text

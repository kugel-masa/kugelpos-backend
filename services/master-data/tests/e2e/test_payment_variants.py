# Copyright 2026 masa@kugel
"""Payment variants (sub-codes) against the running master-data service (issue #311).

Variants cannot be deleted and the e2e tenant outlives a run, so every test
works under payment methods of its own with unique codes, and deletes them at
the end (deleting a payment method takes its variants with it). Nothing is left
on the payment methods other suites pay with.
"""

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import status

pytestmark = pytest.mark.asyncio


def _unique(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6].upper()}"


def _payments_url() -> str:
    return f"/api/v1/tenants/{os.environ.get('TENANT_ID')}/payments"


async def _create_payment(http_client, admin_header, code: str):
    response = await http_client.post(
        _payments_url(),
        json={
            "paymentCode": code,
            "description": "E2E Cashless",
            "limitAmount": 0,
            "canRefund": True,
            "canDepositOver": False,
            "canChange": False,
            "isActive": True,
        },
        headers=admin_header,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text


@pytest_asyncio.fixture
async def two_payment_methods(http_client, admin_header):
    codes = (_unique("PV"), _unique("PV"))
    for code in codes:
        await _create_payment(http_client, admin_header, code)
    yield codes
    for code in codes:
        await http_client.delete(f"{_payments_url()}/{code}", headers=admin_header)


async def _add(http_client, admin_header, payment_code: str, variant_code: str, name: str):
    return await http_client.post(
        f"{_payments_url()}/{payment_code}/variants",
        json={"variantCode": variant_code, "name": name},
        headers=admin_header,
    )


async def test_variants_are_registered_listed_and_carried_by_the_payment(http_client, admin_header, two_payment_methods):
    code, _ = two_payment_methods

    response = await _add(http_client, admin_header, code, "VISA", "VISA")
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["data"]["isActive"] is True
    assert (await _add(http_client, admin_header, code, "PAYPAY", "PayPay")).status_code == status.HTTP_201_CREATED

    listed = await http_client.get(f"{_payments_url()}/{code}/variants", headers=admin_header)
    assert listed.status_code == status.HTTP_200_OK
    assert [v["variantCode"] for v in listed.json()["data"]] == ["PAYPAY", "VISA"]

    payment = await http_client.get(f"{_payments_url()}/{code}", headers=admin_header)
    assert [v["variantCode"] for v in payment.json()["data"]["variants"]] == ["PAYPAY", "VISA"]


async def test_a_duplicate_is_refused_but_another_method_may_use_the_code(http_client, admin_header, two_payment_methods):
    first, second = two_payment_methods
    await _add(http_client, admin_header, first, "VISA", "VISA")

    duplicate = await _add(http_client, admin_header, first, "VISA", "VISA again")
    assert duplicate.status_code == status.HTTP_400_BAD_REQUEST

    other = await _add(http_client, admin_header, second, "VISA", "VISA")
    assert other.status_code == status.HTTP_201_CREATED

    one = await http_client.get(f"{_payments_url()}/{first}/variants/VISA", headers=admin_header)
    assert one.json()["data"]["name"] == "VISA"


async def test_a_variant_is_renamed_stopped_and_resumed(http_client, admin_header, two_payment_methods):
    code, _ = two_payment_methods
    await _add(http_client, admin_header, code, "VISA", "VISA")
    url = f"{_payments_url()}/{code}/variants/VISA"

    renamed = await http_client.put(url, json={"name": "VISA card", "isActive": True}, headers=admin_header)
    assert renamed.status_code == status.HTTP_200_OK
    assert renamed.json()["data"]["name"] == "VISA card"
    assert renamed.json()["data"]["lastUpdateDatetime"] is not None

    stopped = await http_client.put(url, json={"name": "VISA card", "isActive": False}, headers=admin_header)
    assert stopped.json()["data"]["isActive"] is False
    still_listed = await http_client.get(f"{_payments_url()}/{code}/variants", headers=admin_header)
    assert [v["variantCode"] for v in still_listed.json()["data"]] == ["VISA"]

    resumed = await http_client.put(url, json={"name": "VISA card", "isActive": True}, headers=admin_header)
    assert resumed.json()["data"]["isActive"] is True


async def test_a_variant_cannot_be_deleted(http_client, admin_header, two_payment_methods):
    code, _ = two_payment_methods
    await _add(http_client, admin_header, code, "VISA", "VISA")

    response = await http_client.delete(f"{_payments_url()}/{code}/variants/VISA", headers=admin_header)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


async def test_updating_the_payment_method_keeps_its_variants(http_client, admin_header, two_payment_methods):
    code, _ = two_payment_methods
    await _add(http_client, admin_header, code, "VISA", "VISA")

    response = await http_client.put(
        f"{_payments_url()}/{code}",
        json={
            "description": "E2E Cards",
            "limitAmount": 100,
            "canRefund": True,
            "canDepositOver": False,
            "canChange": False,
            "isActive": True,
        },
        headers=admin_header,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert [v["variantCode"] for v in response.json()["data"]["variants"]] == ["VISA"]


async def test_deleting_the_payment_method_takes_its_variants(http_client, admin_header):
    code = _unique("PV")
    await _create_payment(http_client, admin_header, code)
    await _add(http_client, admin_header, code, "VISA", "VISA")

    await http_client.delete(f"{_payments_url()}/{code}", headers=admin_header)
    await _create_payment(http_client, admin_header, code)
    try:
        payment = await http_client.get(f"{_payments_url()}/{code}", headers=admin_header)
        assert payment.json()["data"]["variants"] == []
    finally:
        await http_client.delete(f"{_payments_url()}/{code}", headers=admin_header)


async def test_a_variant_under_an_unknown_method_is_not_found(http_client, admin_header):
    response = await _add(http_client, admin_header, _unique("NONE"), "VISA", "VISA")

    assert response.status_code == status.HTTP_404_NOT_FOUND

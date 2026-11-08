# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Listing transactions by receipt number 0.

The receipt number range comes from RECEIPT_NO_START_VALUE / RECEIPT_NO_END_VALUE
and may start at 0. The list query tested the number for truthiness, so
receipt_no=0 dropped the condition and returned the terminal's transactions
instead of the one with that number.
"""

import os

import pytest
import pytest_asyncio
from fastapi import status

from app.config.settings import settings

BUSINESS_DATE = "20260202"


def _api_headers():
    return {"X-API-KEY": "test-api-key-12345", "Content-Type": "application/json"}


def _tenant_id():
    return os.environ.get("TENANT_ID")


def _tranlog(transaction_no: int, receipt_no: int):
    return {
        "tenant_id": _tenant_id(),
        "store_code": "5678",
        "store_name": "Test Store",
        "terminal_no": 9,
        "business_counter": 1,
        "open_counter": 1,
        "transaction_no": transaction_no,
        "transaction_type": 101,
        "business_date": BUSINESS_DATE,
        "receipt_no": receipt_no,
        "generate_date_time": "2026-02-02T10:00:00",
        "cart_id": f"receipt-zero-{transaction_no}",
        "staff": {"id": "S001", "name": "Test Staff"},
        "line_items": [],
        "payments": [],
        "taxes": [],
        "subtotal_discounts": [],
        "sales": {"total_amount_with_tax": 100.0, "is_cancelled": False},
    }


@pytest_asyncio.fixture
async def receipts_zero_one_and_five():
    from kugel_common.database import database as db_helper

    db = await db_helper.get_db_async(f"db_cart_{_tenant_id()}")
    collection = db[settings.DB_COLLECTION_NAME_TRAN_LOG]
    await collection.delete_many({"business_date": BUSINESS_DATE})
    await collection.insert_many([_tranlog(7700, 0), _tranlog(7701, 1), _tranlog(7705, 5)])
    yield
    await collection.delete_many({"business_date": BUSINESS_DATE})


def _list_url(receipt_no: int) -> str:
    return (
        f"/api/v1/tenants/{_tenant_id()}/stores/5678/terminals/9/transactions"
        f"?terminal_id={_tenant_id()}-5678-9&business_date={BUSINESS_DATE}&receipt_no={receipt_no}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("receipt_no, transaction_no", [(0, 7700), (5, 7705)])
async def test_the_receipt_number_selects_one_transaction(
    http_client, receipts_zero_one_and_five, receipt_no, transaction_no
):
    response = await http_client.get(_list_url(receipt_no), headers=_api_headers())

    assert response.status_code == status.HTTP_200_OK, response.text
    found = [(t["receiptNo"], t["transactionNo"]) for t in response.json()["data"]]
    assert found == [(receipt_no, transaction_no)]

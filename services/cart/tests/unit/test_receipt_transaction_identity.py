# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""The receipt must name the transaction well enough to return it (issue #156).

A return is accepted at any store of the tenant and against any past session, and
the operator has nothing to go on but the printed receipt. Since transaction_no
became the per-open seq it restarts every time the terminal opens, so the number
alone points at many sales — store, register and open epoch have to be printed
with it or the sale cannot be found again.
"""

from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.services.strategies.receipt_data.receipt_data_sample import ReceiptDataSample


STORE_CODE = "5678"
TERMINAL_NO = 9
BUSINESS_COUNTER = 42
TRANSACTION_NO = 7
RECEIPT_NO = 1234


def _sale(transaction_type=101):
    return BaseTransaction(
        tenant_id="T0001",
        store_code=STORE_CODE,
        store_name="Test Store",
        terminal_no=TERMINAL_NO,
        business_date="20260819",
        business_counter=BUSINESS_COUNTER,
        open_counter=1,
        transaction_no=TRANSACTION_NO,
        transaction_type=transaction_type,
        receipt_no=RECEIPT_NO,
        generate_date_time="2026-08-19T10:00:00",
        staff=BaseTransaction.Staff(id="S001", name="Staff1"),
        sales=BaseTransaction.SalesInfo(
            total_amount=1000.0,
            total_amount_with_tax=1100.0,
            total_quantity=1,
        ),
        line_items=[],
        payments=[],
        taxes=[],
        subtotal_discounts=[],
    )


def _receipt_text(tran):
    return ReceiptDataSample("receipt").make_receipt_data(tran).receipt_text


def test_sales_receipt_prints_every_part_of_the_transaction_identity():
    """All four parts, or the sale cannot be located for a return."""
    text = _receipt_text(_sale())

    assert STORE_CODE in text, text
    assert str(TERMINAL_NO) in text, text
    assert str(BUSINESS_COUNTER) in text, text
    assert str(TRANSACTION_NO) in text, text


def test_sales_receipt_labels_the_open_epoch():
    """A bare number is useless to an operator; it needs a label to key on."""
    text = _receipt_text(_sale())

    assert "営業回数" in text, text
    assert "取引通番" in text, text
    assert "店舗コード" in text, text


def test_return_receipt_names_the_original_epoch():
    """The return's own copy must identify the original just as completely.

    Without the epoch the printed original transaction number is ambiguous
    across sessions, so the audit trail on paper cannot be followed back.
    """
    tran = _sale(transaction_type=102)
    tran.origin = BaseTransaction.OriginalTransaction(
        tenant_id="T0001",
        store_code="9999",
        store_name="Other Store",
        terminal_no=3,
        business_counter=17,
        transaction_no=55,
        transaction_type=101,
        receipt_no=99,
        generate_date_time="2026-01-01T10:00:00",
    )

    text = _receipt_text(tran)

    assert "9999" in text, text
    assert "17" in text, text
    assert "55" in text, text
    assert "営業回数" in text, text

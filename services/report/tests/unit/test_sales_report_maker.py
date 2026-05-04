# Copyright 2026 masa@kugel
"""Unit tests for sales report aggregation logic.

`SalesReportMaker` is the largest plugin in the report service (~1100
lines, 80+ branches). It runs MongoDB aggregation pipelines and then
post-processes the results into the report shape exposed via
`/api/v1/.../reports?report_type=sales`.

Pipeline construction is hard to assert without a live mongo, but the
post-processing methods (`_summarize_sales_report`, `_make_sales_gross`,
`_make_sales_net`, `_make_returns`, `_return_factor`) are pure
functions over dicts. Bugs here mean wrong totals on customer-facing
reports — this is exactly issue #107 / #85 territory.
"""
from unittest.mock import AsyncMock

import pytest

from app.enums.transaction_type import TransactionType
from app.services.plugins.sales_report_maker import SalesReportMaker


def _maker() -> SalesReportMaker:
    """Build a maker with mocked repositories. Pure post-processing
    methods don't touch them."""
    return SalesReportMaker(
        tran_repository=AsyncMock(),
        cash_in_out_log_repository=AsyncMock(),
        open_close_log_repository=AsyncMock(),
    )


# ---------------------------------------------------------------------------
# _return_factor — sign convention for transaction types
# ---------------------------------------------------------------------------


class TestReturnFactor:
    def test_normal_sales_factor_is_1(self):
        assert _maker()._return_factor(TransactionType.NormalSales.value) == 1

    def test_void_return_factor_is_1(self):
        """A void of a return cancels the return → adds back. factor=+1."""
        assert _maker()._return_factor(TransactionType.VoidReturn.value) == 1

    def test_return_sales_factor_is_minus_1(self):
        """Customer return subtracts from totals. factor=-1."""
        assert _maker()._return_factor(TransactionType.ReturnSales.value) == -1

    def test_void_sales_factor_is_minus_1(self):
        """A void of a normal sale cancels the sale → subtracts. factor=-1."""
        assert _maker()._return_factor(TransactionType.VoidSales.value) == -1


# ---------------------------------------------------------------------------
# _make_sales_gross — gross = (normal sales' tax-incl + discounts) - voids
# ---------------------------------------------------------------------------


def _normal_result(amount=1000.0, discount=100.0, qty=2, count=1):
    """Mongo aggregation result row for NormalSales."""
    return {
        "_id": {"transaction_type": TransactionType.NormalSales.value},
        "total_amount_with_tax": amount,
        "total_discount_amount": discount,
        "total_quantity": qty,
        "total_transaction_count": count,
    }


def _void_sales_result(amount=0.0, discount=0.0, qty=0, count=0):
    return {
        "_id": {"transaction_type": TransactionType.VoidSales.value},
        "total_amount_with_tax": amount,
        "total_discount_amount": discount,
        "total_quantity": qty,
        "total_transaction_count": count,
    }


def _return_sales_result(amount=0.0, qty=0, count=0):
    return {
        "_id": {"transaction_type": TransactionType.ReturnSales.value},
        "total_amount_with_tax": amount,
        "total_quantity": qty,
        "total_transaction_count": count,
    }


def _void_return_result(amount=0.0, qty=0, count=0):
    return {
        "_id": {"transaction_type": TransactionType.VoidReturn.value},
        "total_amount_with_tax": amount,
        "total_quantity": qty,
        "total_transaction_count": count,
    }


class TestMakeSalesGross:
    def test_normal_sales_only(self):
        """1000 yen tax-incl + 100 yen discount = 1100 yen gross."""
        results = [_normal_result(amount=1000.0, discount=100.0, qty=2, count=1)]
        gross = _maker()._make_sales_gross(results)
        assert gross["amount"] == 1100.0
        assert gross["quantity"] == 2
        assert gross["count"] == 1

    def test_void_sales_subtracts_from_gross(self):
        """A void cancels its original sale: gross excludes the voided amount."""
        results = [
            _normal_result(amount=1000.0, discount=100.0, qty=2, count=1),
            _void_sales_result(amount=500.0, discount=50.0, qty=1, count=1),
        ]
        gross = _maker()._make_sales_gross(results)
        # normal_gross (1100) - void_gross (550) = 550
        assert gross["amount"] == 550.0
        assert gross["quantity"] == 1
        assert gross["count"] == 0

    def test_no_normal_sales_yields_zeroes(self):
        """An empty/no-NormalSales result set gives a zeroed-out gross."""
        gross = _maker()._make_sales_gross([])
        assert gross["amount"] == 0
        assert gross["quantity"] == 0
        assert gross["count"] == 0


# ---------------------------------------------------------------------------
# _make_returns — returns = ReturnSales - VoidReturn
# ---------------------------------------------------------------------------


class TestMakeReturns:
    def test_returns_sums_to_zero_when_void_return_cancels(self):
        results = [
            _return_sales_result(amount=500.0, qty=1, count=1),
            _void_return_result(amount=500.0, qty=1, count=1),
        ]
        ret = _maker()._make_returns(results)
        assert ret["amount"] == 0.0
        assert ret["quantity"] == 0
        assert ret["count"] == 0

    def test_only_returns_present(self):
        results = [_return_sales_result(amount=300.0, qty=2, count=1)]
        ret = _maker()._make_returns(results)
        assert ret["amount"] == 300.0
        assert ret["quantity"] == 2
        assert ret["count"] == 1

    def test_no_data_yields_zero(self):
        ret = _maker()._make_returns([])
        assert ret == {"amount": 0, "quantity": 0, "count": 0}


# ---------------------------------------------------------------------------
# _make_sales_net — net = gross - returns - line-discount - subtotal-discount - tax
# ---------------------------------------------------------------------------


class TestMakeSalesNet:
    def test_simple_net_calculation(self):
        """gross 1100 - returns 0 - line_disc 100 - subtotal_disc 0 - tax 100 = 900."""
        net = _maker()._make_sales_net(
            sales_gross={"amount": 1100.0, "quantity": 5, "count": 2},
            returns={"amount": 0.0, "quantity": 0, "count": 0},
            discount_lineitem={"amount": 100.0},
            discount_subtotal={"amount": 0.0},
            net_tax=100.0,
        )
        assert net["amount"] == 900.0
        assert net["quantity"] == 5
        assert net["count"] == 2

    def test_returns_subtract_from_net(self):
        """If a return came back, net is gross - returns - all discounts - tax."""
        net = _maker()._make_sales_net(
            sales_gross={"amount": 1000.0, "quantity": 5, "count": 2},
            returns={"amount": 200.0, "quantity": 1, "count": 1},
            discount_lineitem={"amount": 0.0},
            discount_subtotal={"amount": 0.0},
            net_tax=80.0,
        )
        # 1000 - 200 - 80 = 720
        assert net["amount"] == 720.0
        # quantity: 5 sold - 1 returned = 4
        assert net["quantity"] == 4
        # count: 2 sales - 1 return = 1
        assert net["count"] == 1


# ---------------------------------------------------------------------------
# _summarize_sales_report — aggregation across transaction types using factors
# ---------------------------------------------------------------------------


def _make_summable(transaction_type: int, **fields):
    """Build a result row with all the fields _summarize_sales_report reads."""
    base = {
        "_id": {"transaction_type": transaction_type},
        "total_amount": 0,
        "total_amount_with_tax": 0,
        "total_tax_amount": 0,
        "total_quantity": 0,
        "total_change_amount": 0,
        "total_discount_amount": 0,
        "total_transaction_count": 0,
        "total_line_items_discount_amount": 0,
        "total_line_items_discount_count": 0,
        "total_line_items_discount_quantity": 0,
        "total_sub_total_discount_amount": 0,
        "total_sub_total_discount_count": 0,
        "total_sub_total_discount_quantity": 0,
        "taxes": [],
        "payments": [],
    }
    base.update(fields)
    return base


class TestSummarizeSalesReport:
    def test_void_sales_subtract_from_summary(self):
        """Void sales contribute with factor -1, cancelling normal sales."""
        results = [
            _make_summable(TransactionType.NormalSales.value, total_amount_with_tax=1000.0,
                          total_quantity=5, total_transaction_count=2),
            _make_summable(TransactionType.VoidSales.value, total_amount_with_tax=400.0,
                          total_quantity=2, total_transaction_count=1),
        ]
        s = _maker()._summarize_sales_report(results)
        # 1000 (factor=1) + 400 (factor=-1) = 600
        assert s["total_amount_with_tax"] == 600.0
        assert s["total_quantity"] == 3
        assert s["total_transaction_count"] == 1

    def test_taxes_aggregated_by_code(self):
        """Multiple results with the same tax_code combine into one entry."""
        results = [
            _make_summable(
                TransactionType.NormalSales.value,
                taxes=[
                    {"tax_code": "01", "tax_name": "10%", "tax_amount": 100.0,
                     "target_amount": 1000.0, "target_quantity": 5},
                    {"tax_code": "11", "tax_name": "8%", "tax_amount": 40.0,
                     "target_amount": 500.0, "target_quantity": 2},
                ],
            ),
        ]
        s = _maker()._summarize_sales_report(results)
        by_code = {t["tax_code"]: t for t in s["taxes"]}
        assert by_code["01"]["tax_amount"] == 100.0
        assert by_code["11"]["tax_amount"] == 40.0

    def test_empty_taxes_array_skipped(self):
        """A result row with no real tax_code (the empty-aggregate case
        from `$group` with no $unwind hits) does not pollute the output."""
        results = [
            _make_summable(
                TransactionType.NormalSales.value,
                taxes=[{"tax_code": None, "tax_name": None, "tax_amount": 0,
                        "target_amount": 0, "target_quantity": 0}],
            ),
        ]
        s = _maker()._summarize_sales_report(results)
        assert s["taxes"] == []

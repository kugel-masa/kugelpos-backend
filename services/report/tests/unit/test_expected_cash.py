# Copyright 2026 masa@kugel
"""The expected-cash formula shared by the sales report and the settlement (#343, R-3)."""
import pytest

from app.services.expected_cash import cash_difference, cash_sales_of, expected_cash, summarize_cash_logs


def test_cash_logs_split_into_in_and_out():
    assert summarize_cash_logs([10000, 500, -2000, -300]) == {
        "cash_in_count": 2,
        "cash_in_amount": 10500,
        "cash_out_count": 2,
        "cash_out_amount": -2300,
    }


def test_only_cash_payments_count_as_cash_sales():
    payments = [
        {"payment_code": "01", "amount": 1200},
        {"payment_code": "11", "amount": 5000},
        {"payment_code": "01", "amount": -200},
    ]
    assert cash_sales_of(payments) == 1000


def test_total_is_cash_sales_plus_in_plus_out():
    # The change reserve (10,000) is a cash-in log written at open: counted once.
    summary = summarize_cash_logs([10000, 500, -2000])
    result = expected_cash(3000, summary)
    assert result == {
        "cash_sales": 3000,
        "cash_in": {"amount": 10500, "count": 2},
        "cash_out": {"amount": -2000, "count": 1},
        "total": 11500,
    }


def test_no_logs_and_no_sales():
    assert expected_cash(0, summarize_cash_logs([]))["total"] == 0


@pytest.mark.parametrize("physical,total,expected", [(11500, 11500, 0), (11000, 11500, -500), (None, 11500, None)])
def test_difference(physical, total, expected):
    assert cash_difference(physical, total) == expected

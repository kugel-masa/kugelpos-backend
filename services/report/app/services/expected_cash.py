# Copyright 2026 masa@kugel
"""
The expected cash in a drawer: the one formula (#343, R-3).

The sales report's cash column and the settlement record both use it, so the
two can never disagree.

    total = cash payments + cash in + cash out      (cash out is negative)

The change reserve is not a separate term: the terminal writes it at open as a
cash-in log, so it is already part of the cash in.
"""

from collections.abc import Iterable
from typing import Optional

CASH_PAYMENT_CODE = "01"


def summarize_cash_logs(amounts: Iterable[float]) -> dict:
    """Split cash log amounts into cash in (positive) and cash out (negative)."""
    amounts = list(amounts)
    cash_in = [a for a in amounts if a > 0]
    cash_out = [a for a in amounts if a < 0]
    return {
        "cash_in_count": len(cash_in),
        "cash_in_amount": sum(cash_in),
        "cash_out_count": len(cash_out),
        "cash_out_amount": sum(cash_out),
    }


def cash_sales_of(payments: Iterable[dict]) -> float:
    """The cash part of a sales report's payment rows."""
    return sum(p["amount"] for p in payments if p.get("payment_code") == CASH_PAYMENT_CODE)


def expected_cash(cash_sales: float, cash_log_summary: dict) -> dict:
    """
    The expected cash and its breakdown.

    Args:
        cash_sales: Net cash payments of the transactions
        cash_log_summary: Output of summarize_cash_logs

    Returns:
        {cash_sales, cash_in {amount, count}, cash_out {amount, count}, total}
    """
    cash_in_amount = cash_log_summary["cash_in_amount"]
    cash_out_amount = cash_log_summary["cash_out_amount"]
    return {
        "cash_sales": cash_sales,
        "cash_in": {"amount": cash_in_amount, "count": cash_log_summary["cash_in_count"]},
        "cash_out": {"amount": cash_out_amount, "count": cash_log_summary["cash_out_count"]},
        "total": cash_sales + cash_in_amount + cash_out_amount,
    }


def cash_difference(physical_amount: Optional[float], total: float) -> Optional[float]:
    """
    Counted minus expected, or None when nothing was counted.

    Zero would print a drawer that was counted and matched; None says nobody
    counted it.
    """
    return None if physical_amount is None else physical_amount - total

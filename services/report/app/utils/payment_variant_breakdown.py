# Copyright 2026 masa@kugel
"""
Summing a report's payments by payment method with a breakdown by variant (issue #311).

A payment line records its payment method (``payment_code``) and, optionally, the
variant it was taken with (``variant_code``). Reports keep one row per payment
method and add the variants under it, so a method is never split into rows by
the variants' names.

Names are taken from the newest sale in the period: each pipeline row carries the
newest ``latest_date_time`` it saw, and a later row replaces the name only when
it is newer, so the result does not depend on the order rows arrive in.
"""

from typing import Any, Optional


def _newer(candidate: Optional[str], current: Optional[str]) -> bool:
    return candidate is not None and (current is None or candidate > current)


def sort_variant_breakdown(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Variants in code order, the line without a variant last."""
    return sorted(variants, key=lambda v: (v.get("variant_code") is None, v.get("variant_code") or ""))


def add_payment_with_variant(rows: list[dict[str, Any]], payment: dict[str, Any], factor: int) -> None:
    """Add one pipeline row of (payment method, variant) to the report's payment rows.

    Args:
        rows: The report's payment rows so far, changed in place. Each has
            ``payment_code``, ``description``, ``amount``, ``count`` and ``variants``.
        payment: A pipeline row with ``payment_code``, ``variant_code``,
            ``description`` (the method's name), ``variant_name``,
            ``latest_date_time``, ``amount`` and ``count``
        factor: The transaction type's sign (1, or -1 for returns and voids)
    """
    payment_code = payment.get("payment_code")
    amount = payment.get("amount", 0) * factor
    count = payment.get("count", 0) * factor
    latest = payment.get("latest_date_time")

    row = next((r for r in rows if r.get("payment_code") == payment_code), None)
    if row is None:
        row = {
            "payment_code": payment_code,
            "description": payment.get("description"),
            "amount": 0,
            "count": 0,
            "variants": [],
            "latest_date_time": latest,
        }
        rows.append(row)
    elif _newer(latest, row.get("latest_date_time")):
        row["description"] = payment.get("description")
        row["latest_date_time"] = latest
    row["amount"] += amount
    row["count"] += count

    variant_code = payment.get("variant_code")
    variant = next((v for v in row["variants"] if v.get("variant_code") == variant_code), None)
    if variant is None:
        variant = {
            "variant_code": variant_code,
            "variant_name": payment.get("variant_name"),
            "amount": 0,
            "count": 0,
            "latest_date_time": latest,
        }
        row["variants"].append(variant)
    elif _newer(latest, variant.get("latest_date_time")):
        variant["variant_name"] = payment.get("variant_name")
        variant["latest_date_time"] = latest
    variant["amount"] += amount
    variant["count"] += count

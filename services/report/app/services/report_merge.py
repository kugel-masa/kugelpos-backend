# Copyright 2026 masa@kugel
"""
Merging frozen daily reports (#343, R-5).

A store's daily report, a terminal's report over several sessions and a
date-range report are the sum of the frozen reports of the settled sessions in
scope. Each function takes the reports as stored (``model_dump()`` dicts, oldest
settlement first) and returns the merged dict; the plugins wrap it into their
document and print it again.

Sessions never overlap, so counts add up: a transaction belongs to one session.
Rows are gathered by their code. A name is taken from the newest report that
has the row, the way the live reports take the newest sale's name.
"""

from typing import Any, Callable, Optional

from app.utils.payment_variant_breakdown import sort_variant_breakdown

AMOUNT_TEMPLATES = ("sales_gross", "sales_net", "discount_for_lineitems", "discount_for_subtotal", "returns")


def _sum_fields(target: dict, source: dict, fields) -> None:
    for f in fields:
        target[f] = (target.get(f) or 0) + (source.get(f) or 0)


def _gather(
    rows_per_report: list[list[dict]],
    key: Callable[[dict], Any],
    sum_fields,
    merge_children: Optional[Callable[[dict, dict], None]] = None,
) -> list[dict]:
    """Rows of all reports gathered by key, in first-seen order; later names win."""
    merged: dict[Any, dict] = {}
    for rows in rows_per_report:
        for row in rows or []:
            k = key(row)
            if k not in merged:
                merged[k] = {**row, **{f: 0 for f in sum_fields}}
                if merge_children:
                    merge_children(merged[k], None)
            current = merged[k]
            # The newest report's descriptive fields (names) win
            for field, value in row.items():
                if field not in sum_fields and not isinstance(value, list) and value is not None:
                    current[field] = value
            _sum_fields(current, row, sum_fields)
            if merge_children:
                merge_children(current, row)
    return list(merged.values())


def _header(reports: list[dict]) -> dict:
    """The fields every report shares; a field the reports disagree on becomes None."""
    first = reports[-1]
    shared = {}
    for field in ("tenant_id", "store_code", "store_name", "terminal_no", "business_date", "open_counter", "business_counter"):
        values = {r.get(field) for r in reports}
        shared[field] = first.get(field) if len(values) == 1 else None
    shared["report_scope"] = "daily"
    shared["report_type"] = first.get("report_type")
    return shared


def merge_sales(reports: list[dict]) -> dict:
    merged = _header(reports)
    for template in AMOUNT_TEMPLATES:
        total: dict = {"amount": 0, "quantity": 0, "count": 0}
        for r in reports:
            _sum_fields(total, r.get(template) or {}, ("amount", "quantity", "count"))
        merged[template] = total

    merged["taxes"] = _gather(
        [r.get("taxes") for r in reports],
        key=lambda t: (t.get("tax_name"), t.get("tax_type")),
        sum_fields=("tax_amount", "target_amount", "target_quantity"),
    )

    def merge_variants(current: dict, row: Optional[dict]) -> None:
        if row is None:
            current["variants"] = []
            return
        current["variants"] = sort_variant_breakdown(
            _gather(
                [current["variants"], row.get("variants")],
                key=lambda v: v.get("variant_code"),
                sum_fields=("amount", "count"),
            )
        )

    merged["payments"] = _gather(
        [r.get("payments") for r in reports],
        key=lambda p: p.get("payment_code") or p.get("payment_name"),
        sum_fields=("amount", "count"),
        merge_children=merge_variants,
    )

    cash = {
        "logical_amount": 0,
        "physical_amount": 0,
        "difference_amount": 0,
        "cash_in": {"amount": 0, "count": 0},
        "cash_out": {"amount": 0, "count": 0},
    }
    uncounted = False
    for r in reports:
        c = r.get("cash") or {}
        cash["logical_amount"] += c.get("logical_amount") or 0
        if c.get("physical_amount") is None:
            uncounted = True
        else:
            cash["physical_amount"] += c["physical_amount"]
            cash["difference_amount"] += c.get("difference_amount") or 0
        for side in ("cash_in", "cash_out"):
            _sum_fields(cash[side], c.get(side) or {}, ("amount", "count"))
    if uncounted:
        # One drawer nobody counted: the total counted cash is unknown, not short
        cash["physical_amount"] = None
        cash["difference_amount"] = None
    merged["cash"] = cash
    return merged


ROW_FIELDS = ("gross_amount", "discount_amount", "net_amount", "quantity", "discount_quantity", "transaction_count")
TOTAL_FIELDS = {
    "total_gross_amount": "gross_amount",
    "total_discount_amount": "discount_amount",
    "total_net_amount": "net_amount",
    "total_quantity": "quantity",
    "total_discount_quantity": "discount_quantity",
    "total_transaction_count": "transaction_count",
}


def _totals_of(reports: list[dict], fields) -> dict:
    """Report totals add up across sessions (a transaction belongs to one session)."""
    return {f: sum((r.get(f) or 0) for r in reports) for f in fields}


def merge_category(reports: list[dict]) -> dict:
    merged = _header(reports)
    merged["categories"] = sorted(
        _gather([r.get("categories") for r in reports], key=lambda c: c.get("category_code"), sum_fields=ROW_FIELDS),
        key=lambda c: c.get("category_code") or "",
    )
    merged.update(_totals_of(reports, TOTAL_FIELDS))
    return merged


CATEGORY_TOTAL_FIELDS = (
    "category_total_gross_amount",
    "category_total_discount_amount",
    "category_total_net_amount",
    "category_total_quantity",
    "category_total_discount_quantity",
    "category_total_transaction_count",
)


def merge_item(reports: list[dict]) -> dict:
    merged = _header(reports)

    def merge_items(current: dict, row: Optional[dict]) -> None:
        if row is None:
            current["items"] = []
            return
        current["items"] = sorted(
            _gather([current["items"], row.get("items")], key=lambda i: i.get("item_code"), sum_fields=ROW_FIELDS),
            key=lambda i: i.get("item_code") or "",
        )

    merged["categories"] = sorted(
        _gather(
            [r.get("categories") for r in reports],
            key=lambda c: c.get("category_code"),
            sum_fields=CATEGORY_TOTAL_FIELDS,
            merge_children=merge_items,
        ),
        key=lambda c: c.get("category_code") or "",
    )
    merged.update(_totals_of(reports, TOTAL_FIELDS))
    return merged


def merge_payment(reports: list[dict]) -> dict:
    merged = _header(reports)

    def merge_variants(current: dict, row: Optional[dict]) -> None:
        if row is None:
            current["variants"] = []
            return
        current["variants"] = sort_variant_breakdown(
            _gather([current["variants"], row.get("variants")], key=lambda v: v.get("variant_code"), sum_fields=("amount", "count"))
        )

    summary = _gather(
        [r.get("payment_summary") for r in reports],
        key=lambda p: p.get("payment_code"),
        sum_fields=("amount", "count"),
        merge_children=merge_variants,
    )
    total_amount = sum(p["amount"] for p in summary)
    for p in summary:
        # The ratio is of the merged total, not an average of the sessions' ratios
        p["ratio"] = round((p["amount"] / total_amount) * 100, 2) if total_amount > 0 else 0.0
    merged["payment_summary"] = summary
    merged["total"] = {"amount": total_amount, "count": sum(p["count"] for p in summary)}
    return merged


PROMOTION_ROW_FIELDS = ("gross_amount", "discount_amount", "net_amount", "quantity", "transaction_count")
PROMOTION_TOTAL_FIELDS = (
    "total_gross_amount",
    "total_discount_amount",
    "total_net_amount",
    "total_quantity",
    "total_transaction_count",
)


def merge_promotion(reports: list[dict]) -> dict:
    merged = _header(reports)
    merged["promotions"] = sorted(
        _gather(
            [r.get("promotions") for r in reports],
            key=lambda p: (p.get("promotion_code"), p.get("promotion_type")),
            sum_fields=PROMOTION_ROW_FIELDS,
        ),
        # As the live report orders them: the biggest discount first
        key=lambda p: -(p.get("discount_amount") or 0),
    )
    merged.update(_totals_of(reports, PROMOTION_TOTAL_FIELDS))
    return merged


def merged_document(document_class, merged: dict, header: dict, receipt_maker=None):
    """
    Wrap a merged report into its document and print it again.

    Args:
        document_class: The plugin's report document class
        merged: Output of a merge_* function
        header: Fields the caller fixes for the merged report (scope, date range...)
        receipt_maker: The plugin's receipt data maker, or None when it has none
    """
    from logging import getLogger

    from kugel_common.utils.misc import get_app_time_str

    values = {**merged, **header, "generate_date_time": get_app_time_str()}
    values.pop("receipt_text", None)
    values.pop("journal_text", None)
    document = document_class(**values)
    if receipt_maker is not None:
        try:
            receipt = receipt_maker.make_receipt_data(document)
            document.receipt_text = receipt.receipt_text
            document.journal_text = receipt.journal_text
        except Exception as e:  # noqa: BLE001 - as the live reports: the figures stand without the print
            getLogger(__name__).warning(f"Could not print the merged {values.get('report_type')} report: {e}")
    return document

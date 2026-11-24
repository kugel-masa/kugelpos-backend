# Copyright 2026 masa@kugel
"""Merging frozen daily reports across sessions (#343, R-5)."""
import pytest

from app.services.report_merge import (
    merge_category,
    merge_item,
    merge_payment,
    merge_promotion,
    merge_sales,
)

HEADER = {"tenant_id": "T", "store_code": "S", "store_name": "S", "report_scope": "daily"}


def _amount(a, q, c):
    return {"amount": a, "quantity": q, "count": c}


def _sales(terminal_no, gross, payments, cash, taxes, business_counter=1, name_suffix=""):
    return {
        **HEADER,
        "terminal_no": terminal_no,
        "business_date": "20261124",
        "open_counter": 1,
        "business_counter": business_counter,
        "report_type": "sales",
        "sales_gross": _amount(gross, 2, 2),
        "sales_net": _amount(gross - 100, 2, 2),
        "discount_for_lineitems": _amount(0, 0, 0),
        "discount_for_subtotal": _amount(0, 0, 0),
        "returns": _amount(0, 0, 0),
        "taxes": taxes,
        "payments": payments,
        "cash": cash,
        "receipt_text": "old",
        "generate_date_time": "x",
    }


def _cash(logical, physical, cin=(0, 0), cout=(0, 0)):
    return {
        "logical_amount": logical,
        "physical_amount": physical,
        "difference_amount": None if physical is None else physical - logical,
        "cash_in": {"amount": cin[0], "count": cin[1]},
        "cash_out": {"amount": cout[0], "count": cout[1]},
    }


class TestSales:
    def test_amounts_taxes_and_payments_add_up(self):
        a = _sales(
            1, 1100,
            [{"payment_code": "01", "payment_name": "Cash", "amount": 1100, "count": 2, "variants": []}],
            _cash(11100, 11100, cin=(10000, 1)),
            [{"tax_name": "10%", "tax_type": None, "tax_amount": 100, "target_amount": 1000, "target_quantity": 2}],
        )
        b = _sales(
            2, 2200,
            [
                {"payment_code": "01", "payment_name": "Cash", "amount": 200, "count": 1, "variants": []},
                {"payment_code": "11", "payment_name": "Card", "amount": 2000, "count": 1,
                 "variants": [{"variant_code": "V", "variant_name": "Visa", "amount": 2000, "count": 1}]},
            ],
            _cash(200, 150),
            [{"tax_name": "10%", "tax_type": None, "tax_amount": 200, "target_amount": 2000, "target_quantity": 2}],
        )

        merged = merge_sales([a, b])

        assert merged["terminal_no"] is None  # two terminals
        assert merged["sales_gross"] == {"amount": 3300, "quantity": 4, "count": 4}
        assert merged["taxes"] == [{"tax_name": "10%", "tax_type": None, "tax_amount": 300, "target_amount": 3000, "target_quantity": 4}]
        cash_row, card_row = merged["payments"]
        assert (cash_row["payment_code"], cash_row["amount"], cash_row["count"]) == ("01", 1300, 3)
        assert card_row["variants"] == [{"variant_code": "V", "variant_name": "Visa", "amount": 2000, "count": 1}]
        assert merged["cash"]["logical_amount"] == 11300
        assert merged["cash"]["physical_amount"] == 11250
        assert merged["cash"]["difference_amount"] == -50
        assert merged["cash"]["cash_in"] == {"amount": 10000, "count": 1}

    def test_one_uncounted_drawer_makes_the_total_unknown(self):
        a = _sales(1, 100, [], _cash(100, 100), [])
        b = _sales(2, 100, [], _cash(100, None), [])

        cash = merge_sales([a, b])["cash"]

        assert cash["logical_amount"] == 200
        assert cash["physical_amount"] is None
        assert cash["difference_amount"] is None

    def test_the_newest_name_wins(self):
        a = _sales(1, 100, [{"payment_code": "01", "payment_name": "Old", "amount": 1, "count": 1, "variants": []}], _cash(0, 0), [])
        b = _sales(1, 100, [{"payment_code": "01", "payment_name": "New", "amount": 1, "count": 1, "variants": []}], _cash(0, 0), [], business_counter=2)

        merged = merge_sales([a, b])

        assert merged["payments"][0]["payment_name"] == "New"
        assert merged["terminal_no"] == 1
        assert merged["business_counter"] is None  # two sessions


def _row(code, gross, qty, tx, **extra):
    return {"gross_amount": gross, "discount_amount": 0, "net_amount": gross, "quantity": qty, "discount_quantity": 0, "transaction_count": tx, **extra}


def _totals(rows):
    return {
        "total_gross_amount": sum(r["gross_amount"] for r in rows),
        "total_discount_amount": 0,
        "total_net_amount": sum(r["net_amount"] for r in rows),
        "total_quantity": sum(r["quantity"] for r in rows),
        "total_discount_quantity": 0,
        "total_transaction_count": sum(r["transaction_count"] for r in rows),
    }


def test_categories_are_gathered_by_code_in_code_order():
    a_rows = [_row("C2", 100, 1, 1, category_code="C2", category_name="Two")]
    b_rows = [_row("C1", 50, 1, 1, category_code="C1", category_name="One"), _row("C2", 200, 2, 2, category_code="C2", category_name="Two!")]
    a = {**HEADER, "report_type": "category", "categories": a_rows, **_totals(a_rows)}
    b = {**HEADER, "report_type": "category", "categories": b_rows, **_totals(b_rows)}

    merged = merge_category([a, b])

    assert [c["category_code"] for c in merged["categories"]] == ["C1", "C2"]
    c2 = merged["categories"][1]
    assert (c2["gross_amount"], c2["quantity"], c2["transaction_count"], c2["category_name"]) == (300, 3, 3, "Two!")
    assert merged["total_gross_amount"] == 350
    assert merged["total_transaction_count"] == 4


def test_items_are_gathered_inside_their_category():
    def category(code, items):
        return {
            "category_code": code, "category_name": code, "items": items,
            "category_total_gross_amount": sum(i["gross_amount"] for i in items),
            "category_total_discount_amount": 0, "category_total_net_amount": sum(i["net_amount"] for i in items),
            "category_total_quantity": sum(i["quantity"] for i in items), "category_total_discount_quantity": 0,
            "category_total_transaction_count": sum(i["transaction_count"] for i in items),
        }

    i1 = _row("I1", 100, 1, 1, item_code="I1", item_name="Item 1")
    i2 = _row("I2", 30, 3, 1, item_code="I2", item_name="Item 2")
    a = {**HEADER, "report_type": "item", "categories": [category("C1", [i1])], **_totals([i1])}
    b = {**HEADER, "report_type": "item", "categories": [category("C1", [i2, i1])], **_totals([i2, i1])}

    merged = merge_item([a, b])

    (c1,) = merged["categories"]
    assert [i["item_code"] for i in c1["items"]] == ["I1", "I2"]
    assert c1["items"][0]["gross_amount"] == 200
    assert c1["category_total_gross_amount"] == 230
    assert merged["total_quantity"] == 5


def test_payment_ratios_are_of_the_merged_total():
    def report(rows):
        return {**HEADER, "report_type": "payment", "payment_summary": rows,
                "total": {"amount": sum(r["amount"] for r in rows), "count": sum(r["count"] for r in rows)}}

    a = report([{"payment_code": "01", "payment_name": "Cash", "amount": 100, "count": 1, "ratio": 100.0, "variants": []}])
    b = report([{"payment_code": "11", "payment_name": "Card", "amount": 300, "count": 1, "ratio": 100.0, "variants": []}])

    merged = merge_payment([a, b])

    assert [(p["payment_code"], p["ratio"]) for p in merged["payment_summary"]] == [("01", 25.0), ("11", 75.0)]
    assert merged["total"] == {"amount": 400, "count": 2}


def test_payment_ratio_with_nothing_paid():
    a = {**HEADER, "report_type": "payment", "payment_summary": [{"payment_code": "01", "payment_name": "Cash", "amount": 0, "count": 0, "ratio": 0.0, "variants": []}], "total": {"amount": 0, "count": 0}}
    assert merge_payment([a])["payment_summary"][0]["ratio"] == 0.0


def test_promotions_biggest_discount_first():
    def promo(code, discount):
        return {"promotion_code": code, "promotion_type": "category", "gross_amount": 1000, "discount_amount": discount,
                "net_amount": 1000 - discount, "quantity": 1, "transaction_count": 1}

    a = {**HEADER, "report_type": "promotion", "promotions": [promo("P1", 100), promo("P2", 50)],
         "total_gross_amount": 2000, "total_discount_amount": 150, "total_net_amount": 1850, "total_quantity": 2, "total_transaction_count": 2}
    b = {**HEADER, "report_type": "promotion", "promotions": [promo("P2", 200)],
         "total_gross_amount": 1000, "total_discount_amount": 200, "total_net_amount": 800, "total_quantity": 1, "total_transaction_count": 1}

    merged = merge_promotion([a, b])

    assert [(p["promotion_code"], p["discount_amount"]) for p in merged["promotions"]] == [("P2", 250), ("P1", 100)]
    assert merged["total_discount_amount"] == 350


@pytest.mark.asyncio
async def test_plugins_build_and_print_merged_documents():
    from unittest.mock import MagicMock

    from app.services.plugins.sales_report_maker import SalesReportMaker

    maker = SalesReportMaker(MagicMock(tenant_id="T"), MagicMock(tenant_id="T"), MagicMock(tenant_id="T"))
    a = _sales(1, 1100, [{"payment_code": "01", "payment_name": "Cash", "amount": 1100, "count": 2, "variants": []}], _cash(1100, 1100), [])

    doc = maker.merge([a, a], business_date="20261124", terminal_no=None)
    saved = maker.from_saved(a)

    assert doc.sales_gross.amount == 2200
    assert doc.terminal_no is None
    assert doc.receipt_text and doc.receipt_text != "old"
    assert saved.receipt_text == "old"

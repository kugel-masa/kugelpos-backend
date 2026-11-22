"""Which payment variant a payment line carries (issue #311)."""

import pytest

from app.exceptions import (
    BadRequestBodyException,
    PaymentVariantInactiveException,
    PaymentVariantNotFoundException,
    PaymentVariantRequiredException,
    ReturnAmountExceedsOriginalException,
    ReturnTenderNotAllowedException,
)
from app.models.documents.cart_document import CartDocument
from app.models.documents.payment_master_document import PaymentMasterDocument, PaymentVariant
from app.services.logics.payment_variant_logic import (
    match_return_payments,
    match_void_payments,
    resolve_sale_variant,
)


def _method(*variants: tuple[str, bool]) -> PaymentMasterDocument:
    return PaymentMasterDocument(
        payment_code="11",
        description="Cashless",
        variants=[PaymentVariant(variant_code=code, name=f"{code} name", is_active=active) for code, active in variants],
    )


# A sale


class TestSale:
    def test_no_variants_and_none_given_records_none(self):
        decision = resolve_sale_variant(_method(), None)

        assert (decision.variant_code, decision.name, decision.builtin_description) == (None, None, "Cashless")

    def test_one_active_variant_is_taken_when_none_is_given(self):
        decision = resolve_sale_variant(_method(("VISA", True), ("JCB", False)), None)

        assert (decision.variant_code, decision.name) == ("VISA", "VISA name")

    def test_several_active_variants_need_one_to_be_given(self):
        with pytest.raises(PaymentVariantRequiredException):
            resolve_sale_variant(_method(("VISA", True), ("JCB", True)), None)

    def test_only_stopped_variants_records_none(self):
        decision = resolve_sale_variant(_method(("VISA", False)), None)

        assert decision.variant_code is None

    @pytest.mark.parametrize("variants", [(), (("VISA", True),), (("VISA", True), ("JCB", True))])
    def test_a_given_active_variant_is_taken(self, variants):
        method = _method(*variants, ("PAYPAY", True))

        decision = resolve_sale_variant(method, "PAYPAY")

        assert (decision.variant_code, decision.name, decision.builtin_description) == (
            "PAYPAY",
            "PAYPAY name",
            "Cashless",
        )

    @pytest.mark.parametrize("variants", [(), (("VISA", True),), (("VISA", True), ("JCB", True))])
    def test_an_unknown_code_is_not_found(self, variants):
        with pytest.raises(PaymentVariantNotFoundException):
            resolve_sale_variant(_method(*variants), "GIFT")

    def test_codes_are_case_sensitive(self):
        with pytest.raises(PaymentVariantNotFoundException):
            resolve_sale_variant(_method(("VISA", True)), "visa")

    @pytest.mark.parametrize("others", [(), (("VISA", True),), (("VISA", True), ("JCB", True))])
    def test_a_stopped_variant_is_refused(self, others):
        with pytest.raises(PaymentVariantInactiveException):
            resolve_sale_variant(_method(*others, ("AMEX", False)), "AMEX")


# A void and a return, against a sale of 11/VISA 1000 and 11/PAYPAY 2000


def _line(code, amount, variant=None, name=None, builtin=None):
    return CartDocument.Payment(
        payment_code=code, amount=amount, variant_code=variant, description=name, builtin_description=builtin
    )


SALE = [
    _line("11", 1000.0, "VISA", "VISA", "Cashless"),
    _line("11", 2000.0, "PAYPAY", "PayPay", "Cashless"),
]


def _pay(code, amount, variant=None):
    payment = {"payment_code": code, "amount": amount}
    if variant is not None:
        payment["variant_code"] = variant
    return payment


class TestVoid:
    def test_each_tender_of_the_sale_is_matched_and_named_as_the_sale_named_it(self):
        decisions = match_void_payments(SALE, [_pay("11", 1000, "VISA"), _pay("11", 2000, "PAYPAY")])

        assert [(d.payment_code, d.variant_code, d.name, d.builtin_description) for d in decisions] == [
            ("11", "VISA", "VISA", "Cashless"),
            ("11", "PAYPAY", "PayPay", "Cashless"),
        ]
        assert all(d.from_original for d in decisions)

    def test_leaving_the_variant_out_does_not_match_a_line_with_one(self):
        with pytest.raises(BadRequestBodyException):
            match_void_payments(SALE, [_pay("11", 3000)])

    def test_an_amount_other_than_the_sale_took_is_refused(self):
        with pytest.raises(BadRequestBodyException):
            match_void_payments(SALE, [_pay("11", 3000, "VISA")])

    @pytest.mark.parametrize("payment", [_pay("11", 1000, "JCB"), _pay("12", 1000), _pay("01", 1000)])
    def test_a_tender_the_sale_did_not_take_is_refused(self, payment):
        with pytest.raises(BadRequestBodyException):
            match_void_payments(SALE, [payment])

    def test_a_sale_without_variants_is_voided_as_before(self):
        sale = [_line("01", 500.0, name="Cash"), _line("11", 300.0, name="Cashless")]

        decisions = match_void_payments(sale, [_pay("01", 500), _pay("11", 300)])

        assert [(d.payment_code, d.variant_code, d.name, d.builtin_description) for d in decisions] == [
            ("01", None, "Cash", None),
            ("11", None, "Cashless", None),
        ]

    def test_lines_of_one_tender_are_summed(self):
        sale = [_line("11", 400.0, "VISA", "VISA"), _line("11", 600.0, "VISA", "VISA")]

        decisions = match_void_payments(sale, [_pay("11", 1000, "VISA")])

        assert decisions[0].variant_code == "VISA"


class TestReturn:
    def test_a_tender_of_the_sale_and_cash_are_taken(self):
        decisions = match_return_payments(SALE, [_pay("11", 2000, "PAYPAY"), _pay("01", 1000)])

        assert [(d.payment_code, d.variant_code, d.name, d.from_original) for d in decisions] == [
            ("11", "PAYPAY", "PayPay", True),
            ("01", None, None, False),
        ]

    def test_cash_alone_is_taken(self):
        decisions = match_return_payments(SALE, [_pay("01", 3000)])

        assert decisions[0].from_original is False

    @pytest.mark.parametrize("payment", [_pay("11", 1000, "JCB"), _pay("12", 1000), _pay("11", 1000)])
    def test_a_tender_neither_of_the_sale_nor_cash_is_refused(self, payment):
        with pytest.raises(ReturnTenderNotAllowedException):
            match_return_payments(SALE, [payment])

    def test_more_than_the_sale_took_by_a_tender_is_refused(self):
        with pytest.raises(ReturnAmountExceedsOriginalException):
            match_return_payments(SALE, [_pay("11", 3000, "VISA")])

    def test_the_limit_counts_a_tender_split_over_lines(self):
        with pytest.raises(ReturnAmountExceedsOriginalException):
            match_return_payments(SALE, [_pay("11", 600, "VISA"), _pay("11", 600, "VISA")])

    def test_up_to_what_the_sale_took_is_taken(self):
        decisions = match_return_payments(SALE, [_pay("11", 500, "VISA"), _pay("11", 500, "VISA"), _pay("01", 2000)])

        assert len(decisions) == 3

    def test_cash_of_the_sale_has_no_limit(self):
        sale = [_line("01", 1000.0, name="Cash"), _line("11", 2000.0, "VISA", "VISA", "Cashless")]

        decisions = match_return_payments(sale, [_pay("01", 3000)])

        assert (decisions[0].from_original, decisions[0].name) == (True, "Cash")

    def test_a_variant_stopped_after_the_sale_is_still_taken(self):
        # Matching is against the sale's lines; the master's active flag is not read.
        decisions = match_return_payments(SALE, [_pay("11", 1000, "VISA")])

        assert (decisions[0].variant_code, decisions[0].name) == ("VISA", "VISA")

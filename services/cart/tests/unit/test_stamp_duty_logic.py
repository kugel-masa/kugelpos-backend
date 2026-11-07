# Copyright 2026 masa@kugel
"""Revenue stamp: levied on the cash received, tax-exclusive, for a completed sale.

x = floor(c * (G - T) / G), with c the cash paid, G the total with tax and T
the total tax. The tier is chosen by x and x is what is recorded.
"""

import pytest
from kugel_common.config.settings_stamp_duty import StampDutySettings
from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction

from app.services.logics.stamp_duty_logic import apply_stamp_duty, stamp_duty_target_amount

MASTER = StampDutySettings().STAMP_DUTY_MASTER


def _tran(total_with_tax, tax, payments, transaction_type=TransactionType.NormalSales.value, cancelled=False):
    tran = BaseTransaction()
    tran.transaction_type = transaction_type
    tran.sales = BaseTransaction.SalesInfo()
    tran.sales.total_amount_with_tax = total_with_tax
    tran.sales.is_cancelled = cancelled
    t = BaseTransaction.Tax()
    t.tax_amount = tax
    tran.taxes = [t]
    tran.payments = []
    for code, amount in payments:
        p = BaseTransaction.Payment()
        p.payment_code = code
        p.amount = amount
        tran.payments.append(p)
    return tran


CASH, CARD = "01", "11"


class TestTheTargetAmount:
    def test_all_cash_is_the_total_without_tax(self):
        assert stamp_duty_target_amount(_tran(55_000, 5_000, [(CASH, 55_000)])) == 50_000

    def test_a_mixed_payment_counts_only_the_cash_share(self):
        # 52,000 * 60,000 / 66,000 = 47,272.7...
        assert stamp_duty_target_amount(_tran(66_000, 6_000, [(CASH, 52_000), (CARD, 14_000)])) == 47_272

    def test_no_cash_is_zero(self):
        assert stamp_duty_target_amount(_tran(66_000, 6_000, [(CARD, 66_000)])) == 0

    def test_decimal_does_not_lose_a_yen(self):
        # 65995 * (61106 / 65995) is 61105.99999999999 in floating point.
        assert stamp_duty_target_amount(_tran(65_995, 65_995 - 61_106, [(CASH, 65_995)])) == 61_106

    def test_a_non_positive_total_is_zero(self):
        assert stamp_duty_target_amount(_tran(0, 0, [(CASH, 0)])) == 0


class TestTheTier:
    def test_the_mixed_payment_below_the_bound_gets_no_stamp(self):
        # Charged 200 yen before: both 60,000 and 52,000 were at least 50,000.
        tran = _tran(66_000, 6_000, [(CASH, 52_000), (CARD, 14_000)])
        apply_stamp_duty(tran, MASTER)
        assert tran.sales.is_stamp_duty_applied is False
        assert tran.sales.stamp_duty_amount == 0

    def test_exactly_the_bound_is_stamped_and_the_target_recorded_is_x(self):
        tran = _tran(55_000, 5_000, [(CASH, 55_000)])
        apply_stamp_duty(tran, MASTER)
        assert tran.sales.is_stamp_duty_applied is True
        assert tran.sales.stamp_duty_amount == 200
        assert tran.sales.stamp_duty_target_amount == 50_000, "the recorded target must be what decided the tier"

    def test_one_yen_below_the_bound_is_not(self):
        tran = _tran(54_999, 5_000, [(CASH, 54_999)])
        apply_stamp_duty(tran, MASTER)
        assert tran.sales.is_stamp_duty_applied is False

    @pytest.mark.parametrize(
        ("without_tax", "duty"),
        [(1_000_000, 200), (1_000_001, 400), (2_000_000, 400), (2_000_001, 600)],
    )
    def test_a_boundary_belongs_to_the_lower_tier(self, without_tax, duty):
        # The rate table cuts "up to 1 million" / "more than 1 million": exactly
        # 1,000,000 is the 200-yen tier.
        tax = without_tax // 10
        tran = _tran(without_tax + tax, tax, [(CASH, without_tax + tax)])
        apply_stamp_duty(tran, MASTER)
        assert tran.sales.stamp_duty_target_amount == without_tax
        assert tran.sales.stamp_duty_amount == duty


class TestWhichTransactions:
    def test_a_cancelled_cart_gets_no_stamp_even_with_cash_entered(self):
        tran = _tran(110_000, 10_000, [(CASH, 110_000)], cancelled=True)
        apply_stamp_duty(tran, MASTER)
        assert tran.sales.is_stamp_duty_applied is False

    @pytest.mark.parametrize(
        "transaction_type",
        [TransactionType.ReturnSales.value, TransactionType.VoidSales.value, TransactionType.VoidReturn.value],
    )
    def test_only_a_normal_sale_is_stamped(self, transaction_type):
        tran = _tran(110_000, 10_000, [(CASH, 110_000)], transaction_type=transaction_type)
        apply_stamp_duty(tran, MASTER)
        assert tran.sales.is_stamp_duty_applied is False

    def test_a_stale_stamp_is_cleared(self):
        tran = _tran(110_000, 10_000, [(CASH, 110_000)], cancelled=True)
        tran.sales.is_stamp_duty_applied = True
        tran.sales.stamp_duty_amount = 200
        tran.sales.stamp_duty_target_amount = 100_000
        apply_stamp_duty(tran, MASTER)
        assert (
            tran.sales.is_stamp_duty_applied,
            tran.sales.stamp_duty_amount,
            tran.sales.stamp_duty_target_amount,
        ) == (
            False,
            0,
            0,
        )

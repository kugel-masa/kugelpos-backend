# Copyright 2026 masa@kugel
"""Unit tests for payment strategy plugins.

Each strategy implements the AbstractPayment contract differently:
  * cash:     allows over-deposit, gives change
  * cashless: rejects over-deposit (no change given)
  * others:   inherits cashless rules

Bugs in these calculations directly affect customer transactions
(missing change, wrong balance, accepted-but-shouldnt'-be payments).
The strategies are pure-state polymorphism — well-suited to unit
testing with a mocked payment-master repository.
"""
from unittest.mock import AsyncMock

import pytest

from app.exceptions import BalanceMinusException, BalanceZeroException, DepositOverException
from app.models.documents.cart_document import CartDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.services.strategies.payments.cash import PaymentByCash
from app.services.strategies.payments.cashless import PaymentByCashless
from app.services.strategies.payments.others import PaymentByOthers
from kugel_common.models.documents.base_tranlog import BaseTransaction


def _make_payment_master(code: str, description: str = "Test") -> PaymentMasterDocument:
    return PaymentMasterDocument(
        payment_code=code, description=description,
        limit_amount=0.0, can_refund=True, can_deposit_over=True,
        can_change=True, is_active=True,
    )


def _make_cart(balance: float = 100.0) -> CartDocument:
    cart = CartDocument()
    cart.balance_amount = balance
    cart.payments = []
    cart.sales = BaseTransaction.SalesInfo()
    cart.sales.change_amount = 0.0
    return cart


def _attach_repo(strategy, payment_code="01"):
    """Wire a mocked payment-master repo so create_cart_payment_async works."""
    repo = AsyncMock()
    repo.base_url = "http://test"
    repo.get_payment_by_code_async = AsyncMock(return_value=_make_payment_master(payment_code))
    strategy.payment_master_repo = repo
    return strategy


# ---------------------------------------------------------------------------
# PaymentByCash
# ---------------------------------------------------------------------------


class TestPaymentByCash:
    @pytest.mark.asyncio
    async def test_exact_amount_zero_change(self):
        """Cash payment matching balance → balance=0, change=0."""
        strategy = _attach_repo(PaymentByCash("01"))
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "01", 100.0, None)

        assert cart.balance_amount == 0.0
        assert cart.sales.change_amount == 0.0
        assert cart.payments[0].amount == 100.0
        assert cart.payments[0].deposit_amount == 100.0

    @pytest.mark.asyncio
    async def test_over_deposit_calculates_change(self):
        """Cash payment > balance → change is set, payment.amount = balance."""
        strategy = _attach_repo(PaymentByCash("01"))
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "01", 150.0, None)

        assert cart.balance_amount == 0.0
        assert cart.sales.change_amount == 50.0
        assert cart.payments[0].amount == 100.0  # capped at balance
        assert cart.payments[0].deposit_amount == 150.0  # original deposit recorded

    @pytest.mark.asyncio
    async def test_under_deposit_partial_payment(self):
        """Cash payment < balance → balance reduces, no change."""
        strategy = _attach_repo(PaymentByCash("01"))
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "01", 30.0, None)

        assert cart.balance_amount == 70.0
        assert cart.sales.change_amount == 0.0
        assert cart.payments[0].amount == 30.0

    @pytest.mark.asyncio
    async def test_zero_balance_raises(self):
        """Paying when balance < 1 raises — would otherwise let users
        'pay' a fully-paid cart."""
        strategy = _attach_repo(PaymentByCash("01"))
        cart = _make_cart(balance=0.0)

        with pytest.raises(BalanceZeroException):
            await strategy.pay(cart, "01", 50.0, None)

    @pytest.mark.asyncio
    async def test_multiple_partial_payments_accumulate(self):
        """Two partial cash payments leave the right remaining balance."""
        strategy = _attach_repo(PaymentByCash("01"))
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "01", 30.0, None)
        await strategy.pay(cart, "01", 20.0, None)

        assert cart.balance_amount == 50.0
        assert len(cart.payments) == 2
        assert cart.payments[0].payment_no == 1
        assert cart.payments[1].payment_no == 2


# ---------------------------------------------------------------------------
# PaymentByCashless
# ---------------------------------------------------------------------------


class TestPaymentByCashless:
    @pytest.mark.asyncio
    async def test_exact_amount_succeeds(self):
        """Cashless matching balance is the most common path."""
        strategy = _attach_repo(PaymentByCashless("11"))
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "11", 100.0, None)

        assert cart.balance_amount == 0.0
        assert cart.sales.change_amount == 0.0  # cashless never gives change

    @pytest.mark.asyncio
    async def test_over_deposit_rejected(self):
        """Cashless > balance must reject — no change is given for cards/digital."""
        strategy = _attach_repo(PaymentByCashless("11"))
        cart = _make_cart(balance=100.0)

        with pytest.raises(DepositOverException):
            await strategy.pay(cart, "11", 150.0, None)

    @pytest.mark.asyncio
    async def test_under_deposit_partial_payment(self):
        """Cashless partial payments allowed (split-pay scenario)."""
        strategy = _attach_repo(PaymentByCashless("11"))
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "11", 60.0, None)

        assert cart.balance_amount == 40.0
        assert cart.payments[0].amount == 60.0


# ---------------------------------------------------------------------------
# PaymentByOthers (inherits cashless rules)
# ---------------------------------------------------------------------------


class TestPaymentByOthers:
    @pytest.mark.asyncio
    async def test_others_inherits_cashless_no_change(self):
        """`others` strategy must follow cashless rules: no over-deposit allowed."""
        strategy = _attach_repo(PaymentByOthers("12"))
        cart = _make_cart(balance=100.0)

        with pytest.raises(DepositOverException):
            await strategy.pay(cart, "12", 200.0, None)


# ---------------------------------------------------------------------------
# Cross-cutting: balance underflow
# ---------------------------------------------------------------------------


class TestBalanceUnderflow:
    @pytest.mark.asyncio
    async def test_cash_payment_negative_balance_raises(self):
        """`update_cart_balance` rejects values that would push balance < 0.
        Without the over-deposit branch (which caps payment.amount), a
        direct balance subtraction larger than balance must raise."""
        from app.services.strategies.payments.abstract_payment import AbstractPayment

        # Construct a barebones AbstractPayment subclass to test the helper.
        class _Probe(AbstractPayment):
            async def pay(self, *a, **kw):
                raise NotImplementedError

            def refund(self, *a, **kw):
                raise NotImplementedError

            async def payment_code(self):
                return "00"

        probe = _Probe()
        cart = _make_cart(balance=10.0)
        with pytest.raises(BalanceMinusException):
            probe.update_cart_balance(cart, payment_amount=20.0)

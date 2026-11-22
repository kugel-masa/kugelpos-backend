# Copyright 2026 masa@kugel
"""Unit tests for payment strategy plugins.

Every strategy settles a payment as its payment master says (issue #309):
  * can_deposit_over false: a deposit above the balance is refused
  * can_deposit_over true:  the payment covers the balance; the excess is
                            change when can_change is true, else kept as deposit
  * limit_amount > 0:       caps what the method covers in the cart

Bugs in these calculations directly affect customer transactions
(missing change, wrong balance, accepted-but-shouldnt'-be payments).
The strategies are pure-state polymorphism — well-suited to unit
testing with a mocked payment-master repository.
"""
from unittest.mock import AsyncMock

import pytest

from app.exceptions import (
    BalanceMinusException,
    BalanceZeroException,
    DepositOverException,
    PaymentLimitExceededException,
)
from app.models.documents.cart_document import CartDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from app.services.strategies.payments.cash import PaymentByCash
from app.services.strategies.payments.cashless import PaymentByCashless
from app.services.strategies.payments.others import PaymentByOthers
from kugel_common.exceptions import NotFoundException, RepositoryException
from kugel_common.models.documents.base_tranlog import BaseTransaction


# The usual settings of each method: cash takes a deposit over the balance and
# gives change; cashless and others take no more than the balance.
CASH = {"can_deposit_over": True, "can_change": True}
NO_OVER_DEPOSIT = {"can_deposit_over": False, "can_change": False}


def _make_payment_master(
    code: str, description: str = "Test", limit_amount: float = 0.0, **settings
) -> PaymentMasterDocument:
    flags = {**(CASH if code == "01" else NO_OVER_DEPOSIT), **settings}
    return PaymentMasterDocument(
        payment_code=code, description=description,
        limit_amount=limit_amount, can_refund=True, is_active=True, **flags,
    )


def _make_cart(balance: float = 100.0) -> CartDocument:
    cart = CartDocument()
    cart.balance_amount = balance
    cart.payments = []
    cart.sales = BaseTransaction.SalesInfo()
    cart.sales.change_amount = 0.0
    return cart


def _attach_repo(strategy, payment_code=None, **master):
    """Wire a mocked payment-master repo; master overrides the method's usual settings."""
    payment_code = payment_code or strategy.payment_code
    repo = AsyncMock(spec=PaymentMasterWebRepository)
    repo.get_payment_by_code_async = AsyncMock(return_value=_make_payment_master(payment_code, **master))
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
        """Cashless > balance is refused when its master does not take a deposit over."""
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
        """`others` follows its master like cashless: no deposit over the balance here."""
        strategy = _attach_repo(PaymentByOthers("12"))
        cart = _make_cart(balance=100.0)

        with pytest.raises(DepositOverException):
            await strategy.pay(cart, "12", 200.0, None)


# ---------------------------------------------------------------------------
# The payment master decides, not the strategy (issue #309)
# ---------------------------------------------------------------------------


class TestThePaymentMasterDecides:
    @pytest.mark.asyncio
    async def test_cash_refuses_a_deposit_over_the_balance_when_its_master_does(self):
        strategy = _attach_repo(PaymentByCash("01"), can_deposit_over=False, can_change=False)
        cart = _make_cart(balance=100.0)

        with pytest.raises(DepositOverException):
            await strategy.pay(cart, "01", 150.0, None)
        assert cart.payments == [] and cart.balance_amount == 100.0

    @pytest.mark.asyncio
    async def test_cashless_gives_change_when_its_master_allows_it(self):
        strategy = _attach_repo(PaymentByCashless("11"), can_deposit_over=True, can_change=True)
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "11", 150.0, None)

        assert cart.balance_amount == 0.0
        assert cart.sales.change_amount == 50.0
        assert (cart.payments[0].amount, cart.payments[0].deposit_amount) == (100.0, 150.0)

    @pytest.mark.parametrize("strategy_class, code", [(PaymentByCash, "01"), (PaymentByOthers, "12")])
    @pytest.mark.asyncio
    async def test_a_deposit_over_without_change_covers_the_balance_and_keeps_the_excess(self, strategy_class, code):
        """A voucher handed over for more than the balance: accepted, no change."""
        strategy = _attach_repo(strategy_class(code), can_deposit_over=True, can_change=False)
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, code, 150.0, None)

        assert cart.balance_amount == 0.0
        assert cart.sales.change_amount == 0.0
        assert (cart.payments[0].amount, cart.payments[0].deposit_amount) == (100.0, 150.0)

    @pytest.mark.asyncio
    async def test_a_payment_over_the_limit_is_refused(self):
        strategy = _attach_repo(PaymentByCashless("11"), limit_amount=50.0)
        cart = _make_cart(balance=100.0)

        with pytest.raises(PaymentLimitExceededException) as exc_info:
            await strategy.pay(cart, "11", 60.0, None)
        assert exc_info.value.error_code == "403017"
        assert cart.payments == [] and cart.balance_amount == 100.0

    @pytest.mark.asyncio
    async def test_the_limit_counts_the_lines_of_a_method_together(self):
        """Splitting a payment does not pass the limit."""
        strategy = _attach_repo(PaymentByCashless("11"), limit_amount=50.0)
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "11", 30.0, None)
        await strategy.pay(cart, "11", 20.0, None)  # up to the limit
        with pytest.raises(PaymentLimitExceededException):
            await strategy.pay(cart, "11", 1.0, None)
        assert cart.balance_amount == 50.0

    @pytest.mark.asyncio
    async def test_the_limit_is_on_what_is_covered_not_on_what_is_handed_over(self):
        """Cash handed over above the balance counts only up to the balance."""
        strategy = _attach_repo(PaymentByCash("01"), limit_amount=100.0)
        cart = _make_cart(balance=100.0)

        await strategy.pay(cart, "01", 150.0, None)

        assert cart.payments[0].amount == 100.0
        assert cart.sales.change_amount == 50.0

    @pytest.mark.asyncio
    async def test_another_method_does_not_count_toward_the_limit(self):
        cart = _make_cart(balance=100.0)
        await _attach_repo(PaymentByCash("01")).pay(cart, "01", 60.0, None)

        await _attach_repo(PaymentByCashless("11"), limit_amount=40.0).pay(cart, "11", 40.0, None)

        assert cart.balance_amount == 0.0

    @pytest.mark.asyncio
    async def test_a_limit_of_zero_means_no_limit(self):
        strategy = _attach_repo(PaymentByCashless("11"), limit_amount=0.0)
        cart = _make_cart(balance=10**7)

        await strategy.pay(cart, "11", 10**7, None)

        assert cart.balance_amount == 0.0


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


# ---------------------------------------------------------------------------
# Payment master lookup failures
# ---------------------------------------------------------------------------


class TestPaymentMasterLookupFailures:
    """The mock follows the real repository's spec, which has no base_url; the
    lookup used to read it while re-wrapping errors, so it raised AttributeError
    (a 500) where an unknown payment code should be a 404."""

    @pytest.mark.asyncio
    async def test_unknown_payment_code_is_not_found(self):
        strategy = _attach_repo(PaymentByCash("01"))
        not_found = NotFoundException(
            message="payment not found for id 99", collection_name="payment web", find_key="99"
        )
        strategy.payment_master_repo.get_payment_by_code_async = AsyncMock(side_effect=not_found)

        with pytest.raises(NotFoundException) as exc_info:
            await strategy.pay(_make_cart(balance=100.0), "99", 100.0, None)

        assert exc_info.value is not_found
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_repository_failure_is_passed_through(self):
        strategy = _attach_repo(PaymentByCash("01"))
        failure = RepositoryException(message="Request error for id 01", collection_name="payment web")
        strategy.payment_master_repo.get_payment_by_code_async = AsyncMock(side_effect=failure)

        with pytest.raises(RepositoryException) as exc_info:
            await strategy.pay(_make_cart(balance=100.0), "01", 100.0, None)

        assert exc_info.value is failure

    @pytest.mark.asyncio
    async def test_unexpected_error_is_wrapped_with_its_cause(self):
        strategy = _attach_repo(PaymentByCash("01"))
        cause = RuntimeError("boom")
        strategy.payment_master_repo.get_payment_by_code_async = AsyncMock(side_effect=cause)

        with pytest.raises(RepositoryException) as exc_info:
            await strategy.pay(_make_cart(balance=100.0), "01", 100.0, None)

        assert not isinstance(exc_info.value, NotFoundException)
        assert exc_info.value.__cause__ is cause

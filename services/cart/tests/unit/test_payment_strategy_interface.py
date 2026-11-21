# Copyright 2026 masa@kugel
"""Every configured payment strategy keeps the interface's calling contract.

pay() and refund() are async, take detail as optional, and accept keyword
arguments beyond their parameters. A strategy that declared only the four
positional parameters would raise TypeError on a caller that passes more.
"""
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.models.documents.cart_document import CartDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from app.services.cart_strategy_manager import CartStrategyManager
from app.services.strategies.payments.abstract_payment import AbstractPayment
from app.services.strategies.payments.cash import PaymentByCash
from app.services.strategies.payments.cashless import PaymentByCashless
from app.services.strategies.payments.others import PaymentByOthers
from kugel_common.models.documents.base_tranlog import BaseTransaction

PLUGINS_JSON = Path(__file__).resolve().parents[2] / "app" / "services" / "strategies" / "plugins.json"
EXTRA_KEYWORDS = {"extra_attribute": None, "another_attribute": 1}
STRATEGIES = [(PaymentByCash, "01"), (PaymentByCashless, "11"), (PaymentByOthers, "12")]


def _configured_payment_strategies():
    with open(PLUGINS_JSON) as f:
        assert json.load(f)["payment_strategies"], "no payment strategy configured"
    return CartStrategyManager().load_strategies("payment_strategies")


def _accepts_any_keyword(method) -> bool:
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(method).parameters.values())


def _strategy(strategy_class, code):
    strategy = strategy_class(code)
    repo = AsyncMock(spec=PaymentMasterWebRepository)
    repo.get_payment_by_code_async = AsyncMock(
        return_value=PaymentMasterDocument(
            payment_code=code, description="Test", limit_amount=0.0, can_refund=True,
            can_deposit_over=True, can_change=True, is_active=True,
        )
    )
    strategy.payment_master_repo = repo
    return strategy


def _cart(balance=1000.0):
    cart = CartDocument()
    cart.balance_amount = balance
    cart.payments = []
    cart.sales = BaseTransaction.SalesInfo()
    cart.sales.change_amount = 0.0
    return cart


@pytest.mark.parametrize("method_name", ["pay", "refund"])
def test_the_interface_declares_the_contract(method_name):
    method = getattr(AbstractPayment, method_name)
    assert inspect.iscoroutinefunction(method)
    assert _accepts_any_keyword(method)
    assert inspect.signature(method).parameters["detail"].default is None


@pytest.mark.parametrize("method_name", ["pay", "refund"])
def test_every_configured_strategy_keeps_the_contract(method_name):
    for strategy in _configured_payment_strategies():
        method = getattr(strategy, method_name)
        name = f"{type(strategy).__name__}.{method_name}"
        assert inspect.iscoroutinefunction(method), f"{name} is not async"
        assert _accepts_any_keyword(method), f"{name} rejects further keywords"
        assert inspect.signature(method).parameters["detail"].default is None, f"{name} requires detail"


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_class, code", STRATEGIES)
async def test_a_payment_with_further_keywords_is_processed_as_without_them(strategy_class, code):
    """The keywords are ignored, not merely tolerated by the signature."""
    results = []
    for call in (
        lambda s, c: s.pay(c, code, 600.0, None),
        lambda s, c: s.pay(c, code, 600.0, **EXTRA_KEYWORDS),  # detail omitted
    ):
        cart = _cart()
        await call(_strategy(strategy_class, code), cart)
        results.append((cart.balance_amount, [(p.amount, p.deposit_amount) for p in cart.payments]))
    assert results[0] == results[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_class, code", STRATEGIES)
async def test_a_refund_can_be_awaited_without_detail_and_with_further_keywords(strategy_class, code):
    strategy = _strategy(strategy_class, code)
    cart = _cart()
    result = await strategy.refund(cart, code, 100.0, **EXTRA_KEYWORDS)
    assert result is cart

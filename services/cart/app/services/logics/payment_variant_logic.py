# Copyright 2026 masa@kugel
"""
Which payment variant (sub-code) a payment line carries (issue #311).

A payment method may have variants: classifications of the payments it takes,
such as card brands under cashless. The variant is identity only; the behaviour
stays with the payment method. These pure functions decide the variant for the
three places a payment line is made:

- **A sale** (``resolve_sale_variant``): a given variant must be an active variant
  of that payment method. With none given, a method with no active variant
  records none, one with exactly one records it, and one with several refuses
  the payment, as the system cannot choose.
- **A void** (``match_void_payments``): a void reverses the sale, so summed by
  ``(payment code, variant)`` its payments must be exactly the sale's tenders, each
  for what the sale took by it. Leaving the variant out means "no variant".
- **A return** (``match_return_payments``): a return refunds by a tender of the
  sale (up to what the sale took by it) or by cash. A variant of the sale is
  taken even if it has been stopped since.

A given code is never silently ignored or replaced by another.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.exceptions import (
    BadRequestBodyException,
    PaymentVariantInactiveException,
    PaymentVariantNotFoundException,
    PaymentVariantRequiredException,
    ReturnAmountExceedsOriginalException,
    ReturnTenderNotAllowedException,
)
from app.models.documents.payment_master_document import PaymentMasterDocument

CASH_PAYMENT_CODE = "01"


@dataclass(frozen=True)
class VariantDecision:
    """The variant a new payment line carries, and the names it is recorded with.

    ``name`` is the variant's name, or None when the line has no variant (the line
    is then named after the payment method). ``builtin_description`` is the payment
    method's name.
    """

    variant_code: Optional[str]
    name: Optional[str]
    builtin_description: Optional[str]


@dataclass(frozen=True)
class RefundLineDecision:
    """How one payment of a void or a return is recorded.

    ``name`` and ``builtin_description`` are the sale's names when the payment
    matched a line of the sale (``from_original``); otherwise None, and the caller
    takes them from the current master.
    """

    payment_code: str
    variant_code: Optional[str]
    name: Optional[str]
    builtin_description: Optional[str]
    from_original: bool


def resolve_sale_variant(pay_doc: PaymentMasterDocument, requested_code: Optional[str]) -> VariantDecision:
    """Decide the variant of a new payment by the payment method's variants.

    Args:
        pay_doc: Payment master of the method the payment is recorded with
        requested_code: Variant code the request gave, or None

    Returns:
        VariantDecision: The variant (None for none) and the names to record

    Raises:
        PaymentVariantNotFoundException: The method has no variant with the given code
        PaymentVariantInactiveException: The given variant is stopped
        PaymentVariantRequiredException: None was given and the method has several active variants
    """
    variants = list(pay_doc.variants or [])
    builtin = pay_doc.description
    if requested_code is not None:
        variant = next((v for v in variants if v.variant_code == requested_code), None)
        if variant is None:
            raise PaymentVariantNotFoundException(
                f"Payment variant not found: payment_code->{pay_doc.payment_code}, variant_code->{requested_code}"
            )
        if not variant.is_active:
            raise PaymentVariantInactiveException(
                f"Payment variant is stopped: payment_code->{pay_doc.payment_code}, variant_code->{requested_code}"
            )
        return VariantDecision(variant.variant_code, variant.name, builtin)

    active = [v for v in variants if v.is_active]
    if not active:
        return VariantDecision(None, None, builtin)
    if len(active) == 1:
        return VariantDecision(active[0].variant_code, active[0].name, builtin)
    raise PaymentVariantRequiredException(
        f"Payment variant required: payment_code->{pay_doc.payment_code}, "
        f"active variants->{sorted(v.variant_code for v in active)}"
    )


def _field(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _key(payment_code: Optional[str], variant_code: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    return payment_code, variant_code


def _sale_tenders(original_lines: Iterable[Any]) -> dict[tuple, dict]:
    """The sale's lines by ``(payment code, variant)``: their total and first line's names."""
    tenders: dict[tuple, dict] = {}
    for line in original_lines or []:
        key = _key(_field(line, "payment_code"), _field(line, "variant_code"))
        tender = tenders.setdefault(
            key,
            {
                "amount": 0.0,
                "name": _field(line, "description"),
                "builtin_description": _field(line, "builtin_description"),
            },
        )
        tender["amount"] += _field(line, "amount") or 0.0
    return tenders


def _require_positive(payments: list[dict]) -> None:
    """A void's or a return's every payment moves money back: its amount must be above zero."""
    for payment in payments:
        amount = payment.get("amount")
        if amount is None or amount <= 0:
            raise BadRequestBodyException(
                f"Refund amount must be greater than 0: payment_code->{payment.get('payment_code')}, "
                f"variant_code->{payment.get('variant_code')}, amount->{amount}"
            )


def _describe(tenders: dict[tuple, dict]) -> str:
    """The sale's tenders, for an error message the client can act on."""
    return ", ".join(f"{code}/{variant or '-'}={tender['amount']}" for (code, variant), tender in tenders.items())


def match_void_payments(original_lines: Iterable[Any], requested: Iterable[dict]) -> list[RefundLineDecision]:
    """Match a void's payments with the sale's lines.

    A void mirrors the sale: summed by ``(payment code, variant)``, the request must
    name exactly the sale's tenders, each for what the sale took by it. A tender may
    be split over several request lines.

    Args:
        original_lines: Payment lines of the sale being voided
        requested: The void's payments (``payment_code``, ``amount``, optional ``variant_code``)

    Returns:
        One decision per requested payment, in request order, named as the sale named it

    Raises:
        BadRequestBodyException: An amount is not above zero, a payment names a tender the
            sale did not take, a tender of the sale is left out, or a tender's total
            differs from what the sale took by it
    """
    requested = list(requested)
    _require_positive(requested)
    tenders = _sale_tenders(original_lines)

    totals: dict[tuple, float] = {}
    for payment in requested:
        key = _key(payment.get("payment_code"), payment.get("variant_code"))
        if key not in tenders:
            raise BadRequestBodyException(
                f"Payment not found in original transaction: payment_code->{key[0]}, variant_code->{key[1]}; "
                f"the sale took {_describe(tenders)}"
            )
        totals[key] = totals.get(key, 0.0) + payment.get("amount")

    for key, tender in tenders.items():
        if totals.get(key, 0.0) != tender["amount"]:
            raise BadRequestBodyException(
                "Payment amount must be equal for void transaction: "
                f"payment_code->{key[0]}, variant_code->{key[1]}, "
                f"payment_amount->{totals.get(key, 0.0)}, payment_amount_original->{tender['amount']}; "
                f"the sale took {_describe(tenders)}"
            )

    decisions = []
    for payment in requested:
        tender = tenders[_key(payment.get("payment_code"), payment.get("variant_code"))]
        decisions.append(
            RefundLineDecision(
                payment.get("payment_code"),
                payment.get("variant_code"),
                tender["name"],
                tender["builtin_description"],
                True,
            )
        )
    return decisions


def match_return_payments(
    original_lines: Iterable[Any], requested: Iterable[dict], cash_code: str = CASH_PAYMENT_CODE
) -> list[RefundLineDecision]:
    """Match a return's payments with the sale's tenders and cash.

    A payment naming a ``(payment code, variant)`` the sale took is refunded to it,
    named as the sale named it; what one such tender refunds, its lines together,
    may not exceed what the sale took by it, except cash. Cash the sale did not
    take is accepted too; its variant is for the caller to decide by the master
    (``from_original=False``).

    Args:
        original_lines: Payment lines of the sale being returned
        requested: The return's payments (``payment_code``, ``amount``, optional ``variant_code``)
        cash_code: Payment code of cash

    Returns:
        One decision per requested payment, in request order

    Raises:
        BadRequestBodyException: An amount is not above zero
        ReturnTenderNotAllowedException: A payment is neither a tender of the sale nor cash
        ReturnAmountExceedsOriginalException: A tender of the sale (cash excepted) would refund
            more than the sale took by it
    """
    requested = list(requested)
    _require_positive(requested)
    tenders = _sale_tenders(original_lines)
    decisions = []
    refunded: dict[tuple, float] = {}
    for payment in requested:
        payment_code = payment.get("payment_code")
        variant_code = payment.get("variant_code")
        key = _key(payment_code, variant_code)
        tender = tenders.get(key)
        if tender is not None:
            decisions.append(
                RefundLineDecision(payment_code, variant_code, tender["name"], tender["builtin_description"], True)
            )
            if payment_code != cash_code:
                refunded[key] = refunded.get(key, 0.0) + (payment.get("amount") or 0.0)
            continue
        if payment_code == cash_code:
            decisions.append(RefundLineDecision(payment_code, variant_code, None, None, False))
            continue
        raise ReturnTenderNotAllowedException(
            "Return tender is neither a tender of the sale nor cash: "
            f"payment_code->{payment_code}, variant_code->{variant_code}; the sale took {_describe(tenders)}"
        )

    for key, amount in refunded.items():
        if amount > tenders[key]["amount"]:
            raise ReturnAmountExceedsOriginalException(
                "Return refunds a tender of the sale more than the sale took by it: "
                f"payment_code->{key[0]}, variant_code->{key[1]}, "
                f"refund->{amount}, sale->{tenders[key]['amount']}"
            )
    return decisions

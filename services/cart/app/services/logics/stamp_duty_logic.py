# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Revenue stamp (収入印紙) on a sale's receipt.

A revenue stamp is due on a receipt for money received. What it is levied on
is the cash received, stated without consumption tax: with c the cash paid, G
the total with tax and T the total tax,

    x = floor(c * (G - T) / G)

When everything is paid in cash, x is simply the total without tax. When cash
is mixed with another tender, only the cash share counts, converted to its
tax-exclusive equivalent in proportion.

The previous rule took the tier whose lower bound was at most BOTH the
tax-exclusive total (over every tender) and the cash amount (with tax), i.e.
``bound <= min(total without tax, cash)``, and recorded the cash amount. A mixed
payment that falls short of the bound got a stamp anyway: 60,000 without tax,
66,000 with, paid 52,000 cash + 14,000 card, gives x = 47,272 and no stamp, but
it was charged 200 yen.

Computed in Decimal and floored at the end: taking the ratio in floating point
first can lose a yen (65,995 with tax, 61,106 without, all cash:
``65995 * (61106 / 65995)`` is 61105.99999999999).

Ported from the stpos fork (2d74ee7e8).
"""

from collections.abc import Iterable
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from kugel_common.enums import TransactionType
from kugel_common.models.documents.base_tranlog import BaseTransaction

# The tender a revenue stamp is levied on: cash.
CASH_PAYMENT_CODE = "01"


def stamp_duty_target_amount(tranlog: BaseTransaction) -> float:
    """
    The amount the stamp is levied on, x = floor(c * (G - T) / G), in whole yen.

    Args:
        tranlog: The transaction

    Returns:
        x, or 0 when the total with tax is not positive
    """
    total_with_tax = Decimal(str(tranlog.sales.total_amount_with_tax or 0))
    if total_with_tax <= 0:
        return 0.0
    tax_total = sum((Decimal(str(tax.tax_amount or 0)) for tax in tranlog.taxes or []), Decimal(0))
    cash_paid = sum(
        (Decimal(str(p.amount or 0)) for p in tranlog.payments or [] if p.payment_code == CASH_PAYMENT_CODE),
        Decimal(0),
    )
    target = cash_paid * (total_with_tax - tax_total) / total_with_tax
    return float(target.to_integral_value(rounding=ROUND_FLOOR))


def clear_stamp_duty(tranlog: BaseTransaction) -> None:
    """Leave the transaction without a stamp."""
    tranlog.sales.is_stamp_duty_applied = False
    tranlog.sales.stamp_duty_target_amount = 0.0
    tranlog.sales.stamp_duty_amount = 0.0


def apply_stamp_duty(tranlog: BaseTransaction, stamp_duty_master: Iterable[dict[str, Any]]) -> None:
    """
    Decide the stamp for a finalized transaction and write it on the tranlog.

    Only a completed normal sale receives money against a receipt. A cancelled
    cart received nothing, even if payments had been entered before it was
    abandoned, so it gets no stamp.

    The master is in descending order and each tier's ``target_amount`` is its
    inclusive lower bound (kugel_common.config.settings_stamp_duty); the first
    tier at or below x is taken. What is recorded as the target is x itself,
    the value the tier was chosen by.

    Args:
        tranlog: The transaction being finalized
        stamp_duty_master: Tiers, highest first
    """
    clear_stamp_duty(tranlog)
    if tranlog.transaction_type != TransactionType.NormalSales.value or tranlog.sales.is_cancelled:
        return
    target = stamp_duty_target_amount(tranlog)
    for tier in stamp_duty_master:
        if tier["target_amount"] <= target:
            tranlog.sales.is_stamp_duty_applied = True
            tranlog.sales.stamp_duty_target_amount = target
            tranlog.sales.stamp_duty_amount = float(tier["stamp_duty_amount"])
            break

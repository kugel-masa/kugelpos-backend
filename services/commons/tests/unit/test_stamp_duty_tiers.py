# Copyright 2026 masa@kugel
"""The stamp duty tiers against the National Tax Agency rate table (No. 7141, document No. 17).

The table is cut as "50,000 yen or more, up to 1 million", "more than 1 million,
up to 2 million", ... "more than 1 billion". Each boundary and the yen on either
side are checked, using the same lookup the cart does: the first tier, highest
first, with ``target_amount <= x``.
"""

import pytest

from kugel_common.config.settings_stamp_duty import StampDutySettings

MASTER = StampDutySettings().STAMP_DUTY_MASTER

# (upper bound of a tier, inclusive, in yen; duty for amounts up to it)
RATE_TABLE = [
    (1_000_000, 200),
    (2_000_000, 400),
    (3_000_000, 600),
    (5_000_000, 1_000),
    (10_000_000, 2_000),
    (20_000_000, 4_000),
    (30_000_000, 6_000),
    (50_000_000, 10_000),
    (100_000_000, 20_000),
    (200_000_000, 40_000),
    (300_000_000, 60_000),
    (500_000_000, 100_000),
    (1_000_000_000, 150_000),
]
ABOVE_ONE_BILLION = 200_000


def _duty(x: int) -> int:
    for tier in MASTER:
        if tier["target_amount"] <= x:
            return tier["stamp_duty_amount"]
    return 0


def test_below_50000_is_exempt():
    assert _duty(49_999) == 0


def test_50000_is_the_first_tier():
    # "50,000 yen or more": the one bound that is inclusive in the table itself.
    assert _duty(50_000) == 200


@pytest.mark.parametrize("upper, duty", RATE_TABLE)
def test_each_upper_bound_belongs_to_its_own_tier(upper, duty):
    # Exactly 1,000,000 is "up to 1 million" -> 200 yen, not the 400-yen tier.
    assert _duty(upper - 1) == duty
    assert _duty(upper) == duty


@pytest.mark.parametrize(
    "upper, next_duty",
    [(upper, nxt) for (upper, _), (_, nxt) in zip(RATE_TABLE, RATE_TABLE[1:] + [(None, ABOVE_ONE_BILLION)])],
)
def test_one_yen_above_moves_to_the_next_tier(upper, next_duty):
    assert _duty(upper + 1) == next_duty


def test_the_master_is_highest_first():
    bounds = [t["target_amount"] for t in MASTER]
    assert bounds == sorted(bounds, reverse=True)

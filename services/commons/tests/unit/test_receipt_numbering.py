# Copyright 2026 masa@kugel
"""Unit tests for receipt number derivation (issue #166).

One running counter, two views: the counter only ever increases (so the
terminal's open-time max() reconcile stays correct) and the printed number is
derived from it, wrapping inside the configured range.
"""

import pytest

from kugel_common.utils.receipt_numbering import (
    derive_receipt_no,
    receipt_cycle,
    receipt_range_width,
)

# Deliberately tiny range so a wrap is reachable in a test.
START, END = 111111, 111115


class TestReceiptRangeWidth:
    def test_counts_both_ends(self):
        assert receipt_range_width(START, END) == 5

    def test_single_number_range(self):
        assert receipt_range_width(500, 500) == 1

    def test_empty_range_is_rejected(self):
        with pytest.raises(ValueError):
            receipt_range_width(999, 111)


class TestDeriveReceiptNo:
    def test_first_transaction_prints_the_start_value(self):
        assert derive_receipt_no(1, START, END) == START

    def test_counts_up_within_the_range(self):
        assert [derive_receipt_no(n, START, END) for n in range(1, 6)] == [
            111111,
            111112,
            111113,
            111114,
            111115,
        ]

    def test_wraps_back_to_start(self):
        assert derive_receipt_no(6, START, END) == START
        assert derive_receipt_no(7, START, END) == 111112

    def test_second_wrap(self):
        assert derive_receipt_no(11, START, END) == START

    def test_default_production_range(self):
        # The shipped defaults: 111111..999999.
        assert derive_receipt_no(1, 111111, 999999) == 111111
        assert derive_receipt_no(888889, 111111, 999999) == 999999
        assert derive_receipt_no(888890, 111111, 999999) == 111111

    def test_counter_below_one_maps_to_start(self):
        # Nothing counted yet: a freshly seeded terminal reports 0.
        assert derive_receipt_no(0, START, END) == START
        assert derive_receipt_no(-5, START, END) == START

    def test_single_number_range_always_prints_it(self):
        assert [derive_receipt_no(n, 500, 500) for n in (1, 2, 3)] == [500, 500, 500]

    def test_result_never_leaves_the_range(self):
        assert all(START <= derive_receipt_no(n, START, END) <= END for n in range(1, 200))

    def test_empty_range_is_rejected(self):
        with pytest.raises(ValueError):
            derive_receipt_no(1, 999, 111)


class TestReceiptCycle:
    def test_first_cycle_is_zero(self):
        assert [receipt_cycle(n, START, END) for n in range(1, 6)] == [0, 0, 0, 0, 0]

    def test_increments_on_wrap(self):
        assert receipt_cycle(6, START, END) == 1
        assert receipt_cycle(10, START, END) == 1
        assert receipt_cycle(11, START, END) == 2

    def test_unstarted_counter_is_cycle_zero(self):
        assert receipt_cycle(0, START, END) == 0

    def test_cycle_and_number_reconstruct_the_counter(self):
        # The pair is derivable, which is why it is not stored.
        for counter in range(1, 60):
            cycle = receipt_cycle(counter, START, END)
            printed = derive_receipt_no(counter, START, END)
            assert cycle * receipt_range_width(START, END) + (printed - START) + 1 == counter


class TestMonotonicity:
    def test_counter_order_survives_a_wrap(self):
        # The property the whole design rests on: comparing counters is valid
        # across a wrap, comparing printed numbers is not.
        before_wrap, after_wrap = 5, 6
        assert before_wrap < after_wrap
        assert derive_receipt_no(before_wrap, START, END) > derive_receipt_no(after_wrap, START, END)

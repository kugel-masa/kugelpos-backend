# Copyright 2026 masa@kugel
"""What a settlement counts from the transactions that have arrived (#343, R-2, R-13).

The carried series (rows with a receipt_counter) is numbered 1..N within a
session, so its gaps and duplicates mean something. The server series (no
receipt_counter) is numbered terminal-wide and is only counted.
"""
import pytest

from app.services.settlement_counting import (
    TranRow,
    count_session,
    missing_cash_log_count,
    to_ranges,
)


def carried(no, cart=None):
    return TranRow(cart_id=cart if cart is not None else f"c{no}", transaction_no=no, receipt_counter=no)


def server(no, cart=None):
    return TranRow(cart_id=cart if cart is not None else f"s{no}", transaction_no=no, receipt_counter=None)


class TestToRanges:
    def test_empty(self):
        assert to_ranges([]) == []

    def test_runs(self):
        assert to_ranges([1, 2, 3, 5, 7, 8]) == [
            {"first": 1, "last": 3},
            {"first": 5, "last": 5},
            {"first": 7, "last": 8},
        ]

    def test_unsorted_and_repeated_input(self):
        assert to_ranges([3, 1, 2, 2]) == [{"first": 1, "last": 3}]


class TestIncludedCount:
    def test_counts_carts_not_rows(self):
        rows = [carried(1, "a"), carried(1, "a"), carried(2, "b")]
        assert count_session(rows, None).included_count == 2

    def test_rows_without_cart_id_count_one_each(self):
        rows = [TranRow(cart_id=None, transaction_no=1, receipt_counter=1), TranRow(cart_id=None, transaction_no=2, receipt_counter=2)]
        assert count_session(rows, None).included_count == 2

    @pytest.mark.parametrize("no", [None, 0, -1])
    def test_unnumbered_rows_are_left_out(self, no):
        rows = [carried(1), TranRow(cart_id="x", transaction_no=no, receipt_counter=None)]
        result = count_session(rows, None)
        assert result.included_count == 1
        assert result.server_numbered_count == 0

    def test_both_series_are_counted(self):
        rows = [carried(1), carried(2), server(1001), server(1002)]
        result = count_session(rows, None)
        assert result.included_count == 4
        assert result.server_numbered_count == 2


class TestMissing:
    def test_declared_count_names_leading_and_trailing_gaps(self):
        result = count_session([carried(2), carried(3)], declared_seq=5)
        assert result.missing_ranges == [{"first": 1, "last": 1}, {"first": 4, "last": 5}]
        assert result.missing_count == 3

    def test_without_declaration_only_holes_between_arrivals(self):
        result = count_session([carried(2), carried(5)], declared_seq=None)
        assert result.missing_ranges == [{"first": 3, "last": 4}]
        assert result.missing_count == 2

    def test_nothing_arrived_and_nothing_declared(self):
        result = count_session([], declared_seq=None)
        assert result.missing_count == 0
        assert result.missing_ranges == []
        assert result.included_ranges == []

    def test_nothing_arrived_with_declaration(self):
        result = count_session([], declared_seq=3)
        assert result.missing_ranges == [{"first": 1, "last": 3}]

    def test_declared_zero(self):
        result = count_session([], declared_seq=0)
        assert result.missing_count == 0

    def test_numbers_above_the_declaration_are_included_not_missing(self):
        result = count_session([carried(1), carried(2), carried(4)], declared_seq=2)
        assert result.missing_count == 0
        assert result.included_ranges == [{"first": 1, "last": 2}, {"first": 4, "last": 4}]

    def test_server_series_never_makes_carried_numbers_look_missing(self):
        # DUAL: carried 1..3 and server numbers 1041, 1042 in one session.
        rows = [carried(1), carried(2), carried(3), server(1041), server(1042)]
        result = count_session(rows, declared_seq=3)
        assert result.missing_count == 0
        assert result.duplicate_numbers == []
        assert result.included_ranges == [{"first": 1, "last": 3}]


class TestDuplicates:
    def test_same_number_on_different_carts(self):
        rows = [carried(1, "a"), carried(2, "b"), carried(2, "c")]
        assert count_session(rows, None).duplicate_numbers == [2]

    def test_same_cart_twice_is_not_a_duplicate(self):
        rows = [carried(2, "a"), carried(2, "a")]
        assert count_session(rows, None).duplicate_numbers == []

    def test_server_number_equal_to_a_carried_number_is_not_a_duplicate(self):
        rows = [carried(5, "a"), server(5, "b")]
        assert count_session(rows, None).duplicate_numbers == []


class TestMissingCashLogs:
    @pytest.mark.parametrize(
        "declared,received,expected",
        [(None, 3, 0), (3, 3, 0), (4, 3, 1), (2, 3, 0), (0, 0, 0)],
    )
    def test_difference_never_below_zero(self, declared, received, expected):
        assert missing_cash_log_count(declared, received) == expected

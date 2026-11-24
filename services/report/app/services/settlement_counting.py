# Copyright 2026 masa@kugel
"""
Counting the transactions a settlement is based on (#343).

Pure functions over the transactions that have arrived for one session. Two
numbering series can meet in a session:

- the carried series: a client that carries its cart numbers them 1..N within
  the session and records a ``receipt_counter``. Gaps and repeats in this series
  mean a transaction has not arrived, or was numbered twice;
- the server series: the legacy path numbers transactions terminal-wide and
  records no ``receipt_counter``. Those numbers do not start at 1 and are not
  analysed for gaps; they are only counted.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class TranRow:
    """The fields of a transaction log that counting needs."""

    cart_id: Optional[str]
    transaction_no: Optional[int]
    receipt_counter: Optional[int]


@dataclass
class SessionCount:
    """What a settlement records about the transactions of its session."""

    included_count: int = 0
    included_ranges: list[dict] = field(default_factory=list)
    missing_count: int = 0
    missing_ranges: list[dict] = field(default_factory=list)
    duplicate_numbers: list[int] = field(default_factory=list)
    server_numbered_count: int = 0


def to_ranges(numbers) -> list[dict]:
    """Collapse numbers into runs: ``[1, 2, 3, 5]`` -> ``[{first: 1, last: 3}, {first: 5, last: 5}]``."""
    ordered = sorted(set(numbers))
    ranges: list[dict] = []
    for n in ordered:
        if ranges and ranges[-1]["last"] == n - 1:
            ranges[-1]["last"] = n
        else:
            ranges.append({"first": n, "last": n})
    return ranges


def _identity(row: TranRow, index: int) -> str:
    # A row without a cart_id is its own transaction.
    return row.cart_id if row.cart_id is not None else f"__row_{index}"


def count_session(rows: list[TranRow], declared_seq: Optional[int]) -> SessionCount:
    """
    Count one session's transactions.

    Args:
        rows: Every transaction log of the session that has arrived, cancelled
            ones included (they carry a number too)
        declared_seq: The last carried number the terminal says it issued, or
            None when it did not say. When given, missing numbers are counted
            over 1..declared_seq; otherwise only the gaps between the numbers
            that arrived. The count is never guessed.

    Returns:
        SessionCount
    """
    numbered = [(i, r) for i, r in enumerate(rows) if r.transaction_no is not None and r.transaction_no >= 1]

    included = {_identity(r, i) for i, r in numbered}
    server_ids = {_identity(r, i) for i, r in numbered if r.receipt_counter is None}

    carts_by_number: dict[int, set[str]] = {}
    for i, r in numbered:
        if r.receipt_counter is None:
            continue
        carts_by_number.setdefault(r.transaction_no, set()).add(_identity(r, i))

    carried_numbers = set(carts_by_number)
    if declared_seq is not None:
        expected = set(range(1, declared_seq + 1))
    elif carried_numbers:
        expected = set(range(min(carried_numbers), max(carried_numbers) + 1))
    else:
        expected = set()
    missing = expected - carried_numbers

    return SessionCount(
        included_count=len(included),
        included_ranges=to_ranges(carried_numbers),
        missing_count=len(missing),
        missing_ranges=to_ranges(missing),
        duplicate_numbers=sorted(n for n, carts in carts_by_number.items() if len(carts) > 1),
        server_numbered_count=len(server_ids),
    )


def missing_cash_log_count(declared: Optional[int], received: int) -> int:
    """Cash logs the terminal recorded that have not arrived; 0 when it did not say."""
    if declared is None:
        return 0
    return max(declared - received, 0)

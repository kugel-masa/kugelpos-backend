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
Receipt numbering: one running counter, two views (issue #166).

The terminal carries a single monotonic ``receipt_counter`` - the number of
transactions it has finalized - and the customer-facing ``receipt_no`` is a
pure function of it and the configured range:

    receipt_no = start + ((receipt_counter - 1) mod (end - start + 1))

Keeping the wrap in the *derivation* rather than in the stored counter is what
lets the terminal's open-time ``max()`` reconcile stay correct: a counter that
only ever increases can be compared, a printed number that cycles cannot.

The range comes from the master-data settings hierarchy
(``RECEIPT_NO_START_VALUE`` / ``RECEIPT_NO_END_VALUE``), so a POS client reads
it the same way it reads any other terminal setting.
"""


def receipt_range_width(start: int, end: int) -> int:
    """
    Number of distinct receipt numbers in a configured range.

    Args:
        start: First printed receipt number
        end: Last printed receipt number, after which numbering wraps

    Returns:
        Count of numbers in [start, end]

    Raises:
        ValueError: The range is empty (end below start)
    """
    if end < start:
        raise ValueError(f"Receipt number range is empty: start={start} end={end}")
    return end - start + 1


def derive_receipt_no(counter: int, start: int, end: int) -> int:
    """
    Map a running receipt counter onto the configured printed range.

    Args:
        counter: The terminal's running receipt counter, 1-based. Values below
            1 mean nothing has been counted yet and map to `start`.
        start: First printed receipt number
        end: Last printed receipt number, after which numbering wraps

    Returns:
        The receipt number to print for this counter value

    Raises:
        ValueError: The range is empty (end below start)
    """
    width = receipt_range_width(start, end)
    if counter < 1:
        return start
    return start + ((counter - 1) % width)


def receipt_cycle(counter: int, start: int, end: int) -> int:
    """
    How many times the printed range has wrapped at this counter value.

    Not stored anywhere - it is derivable, and it exists so that a log line or
    an audit query can say which cycle a repeated receipt number belongs to.

    Args:
        counter: The terminal's running receipt counter, 1-based
        start: First printed receipt number
        end: Last printed receipt number

    Returns:
        Zero-based cycle index (0 until the first wrap)

    Raises:
        ValueError: The range is empty (end below start)
    """
    width = receipt_range_width(start, end)
    if counter < 1:
        return 0
    return (counter - 1) // width

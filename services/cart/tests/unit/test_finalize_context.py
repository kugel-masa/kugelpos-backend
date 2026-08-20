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
"""Unit tests for FinalizeContext validation (issue #156 review fixes M1/M2)."""
import pytest
from pydantic import ValidationError

from app.api.v1.schemas import FinalizeContext


def test_empty_context_is_valid():
    """A body-less bill (no carried context) parses fine."""
    ctx = FinalizeContext()
    assert ctx.seq is None and ctx.receipt_no is None and ctx.transaction_datetime is None


def test_full_context_is_valid():
    ctx = FinalizeContext(seq=5, receiptNo=10, transactionDatetime="2026-06-14T09:30:00")
    assert ctx.seq == 5
    assert ctx.receipt_no == 10
    assert ctx.transaction_datetime == "2026-06-14T09:30:00"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"transactionDatetime": "2026-06-14T09:30:00"},  # only time
        {"seq": 5},  # only seq
        {"seq": 5, "receiptNo": 10},  # missing time
        {"seq": 5, "transactionDatetime": "2026-06-14T09:30:00"},  # missing receipt
    ],
)
def test_partial_context_is_rejected(kwargs):
    """M1: the three finalize fields are all-or-nothing — a partial context
    would write a null transaction_no/receipt_no, so it must be rejected."""
    with pytest.raises(ValidationError):
        FinalizeContext(**kwargs)


@pytest.mark.parametrize(
    "bad_datetime",
    [
        "2026-06-14 09:30:00",  # space separator, no 'T'
        "2026-06-14",  # date only
        "not-a-date",
        "1718354400",  # epoch
    ],
)
def test_bad_datetime_is_rejected(bad_datetime):
    """M2: a non-ISO datetime would corrupt the generate_date_time / business
    bucketing (split on 'T'), so it must be rejected."""
    with pytest.raises(ValidationError):
        FinalizeContext(seq=5, receiptNo=10, transactionDatetime=bad_datetime)

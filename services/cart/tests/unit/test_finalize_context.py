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
from datetime import timedelta

import pytest
from pydantic import ValidationError

from kugel_common.utils.misc import get_app_time

from app.api.v1.schemas import MAX_BACKDATED_FINALIZE, MAX_FUTUREDATED_FINALIZE, FinalizeContext


def _stamp(offset: timedelta = timedelta(0)) -> str:
    """A naive ISO datetime relative to the server clock the validator reads.

    The validator only accepts times within a window around now, so a literal
    date in a test turns into a failure once the window has moved past it.
    """
    return (get_app_time().replace(tzinfo=None, microsecond=0) + offset).isoformat()


NOW = _stamp()


def test_empty_context_is_valid():
    """A body-less bill (no carried context) parses fine."""
    ctx = FinalizeContext()
    assert ctx.seq is None and ctx.receipt_counter is None and ctx.transaction_datetime is None


def test_full_context_is_valid():
    ctx = FinalizeContext(seq=5, receiptCounter=10, transactionDatetime=NOW)
    assert ctx.seq == 5
    assert ctx.receipt_counter == 10
    assert ctx.transaction_datetime == NOW


@pytest.mark.parametrize(
    "kwargs",
    [
        {"transactionDatetime": NOW},  # only time
        {"seq": 5},  # only seq
        {"seq": 5, "receiptCounter": 10},  # missing time
        {"seq": 5, "transactionDatetime": NOW},  # missing counter
    ],
)
def test_partial_context_is_rejected(kwargs):
    """M1: the three finalize fields are all-or-nothing — a partial context
    would write a null transaction_no or receipt_no, so it must be rejected."""
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
        FinalizeContext(seq=5, receiptCounter=10, transactionDatetime=bad_datetime)


@pytest.mark.parametrize(
    "offset",
    [
        -MAX_BACKDATED_FINALIZE + timedelta(hours=1),  # an offline session settled late
        MAX_FUTUREDATED_FINALIZE - timedelta(hours=1),  # a terminal clock running ahead
    ],
)
def test_datetime_inside_the_window_is_accepted(offset):
    ctx = FinalizeContext(seq=5, receiptCounter=10, transactionDatetime=_stamp(offset))
    assert ctx.transaction_datetime == _stamp(offset)


@pytest.mark.parametrize(
    "offset",
    [
        -MAX_BACKDATED_FINALIZE - timedelta(hours=1),
        MAX_FUTUREDATED_FINALIZE + timedelta(hours=1),
    ],
)
def test_datetime_outside_the_window_is_rejected(offset):
    """A well-formed but plainly wrong clock lands the sale in a business date
    that reports never reconcile."""
    with pytest.raises(ValidationError):
        FinalizeContext(seq=5, receiptCounter=10, transactionDatetime=_stamp(offset))

# Copyright 2025 masa@kugel
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
"""Unit tests for the `mid` column explicit-width / align rendering (#143).

The `mid` cell is [startCol, startCol + width); `align` operates within it.
`left`/`right` keep their anchor-based behavior. Production receipts only emit
left+right pairs, so those stay byte-equivalent (covered elsewhere)."""
import pytest
import wcwidth

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.print_document_model import Column, ColumnsElement
from kugel_common.receipt.receipt_data_model import Page


def _disp_slice(text: str, start: int, end: int) -> str:
    """Slice ``text`` by display column (wcwidth), not character index, so
    assertions hold when wide (full-width) characters precede the region."""
    out = ""
    col = 0
    for ch in text:
        if start <= col < end:
            out += ch
        col += wcwidth.wcwidth(ch)
    return out


class _Strategy(AbstractReceiptData):
    def make_receipt_header(self, model, page: Page):
        pass

    def make_receipt_body(self, model, page: Page):
        pass

    def make_receipt_footer(self, model, page: Page):
        pass


@pytest.fixture
def strategy():
    return _Strategy("default", 48)


def _render(strategy, columns, width=48):
    return strategy._render_columns_element(ColumnsElement(columns=columns), width)


# ---- cell alignment (independent of wide-char positioning) ----


def test_cell_align_right_left_pads_within_cell():
    # value width 7 inside a width-10 cell -> 3 leading spaces, no trailing.
    assert AbstractReceiptData._render_mid_cell("@108 x1", 10, "right") == "   @108 x1"


def test_cell_align_left_is_default():
    # "2点" display width 3 (1 + 2) inside a width-8 cell -> 5 trailing spaces.
    assert AbstractReceiptData._render_mid_cell("2点", 8, None) == "2点     "
    assert AbstractReceiptData._render_mid_cell("2点", 8, "left") == "2点     "


def test_cell_align_center():
    # value width 2 inside width-6 cell -> 2 left, 2 right.
    assert AbstractReceiptData._render_mid_cell("ab", 6, "center") == "  ab  "
    # odd remainder favors the right side (floor on the left).
    assert AbstractReceiptData._render_mid_cell("ab", 7, "center") == "  ab   "


def test_cell_value_wider_than_cell_overflows_with_no_padding():
    assert AbstractReceiptData._render_mid_cell("ABCDEF", 3, "right") == "ABCDEF"
    assert AbstractReceiptData._render_mid_cell("ABCDEF", 3, "left") == "ABCDEF"


# ---- positioning within a full columns line (ASCII left so char==display col) ----


def test_mid_cell_positioned_at_start_col(strategy):
    line = _render(
        strategy,
        [
            Column(slot="left", value="Tea"),  # width 3
            Column(slot="mid", value="@1", start_col=10, width=6, align="right"),
            Column(slot="right", value="108"),
        ],
    )
    # cell [10, 16): "@1" right-justified -> 4 spaces then "@1".
    assert line[10:16] == "    @1"


def test_mid_without_width_keeps_legacy_behavior(strategy):
    """A mid column with no width places the value at startCol (align ignored)."""
    line = _render(
        strategy,
        [
            Column(slot="left", value="ST"),
            Column(slot="mid", value="2pt", start_col=10, align="right"),
            Column(slot="right", value="258"),
        ],
    )
    assert line[10:13] == "2pt"  # value sits exactly at startCol, no left padding


def test_mid_width_colliding_with_right_keeps_min_one_space(strategy):
    """When a wide mid cell would overrun the right column, the renderer still
    emits both values with at least one separating space (no truncation, no
    crash) — truncation on collision is the consumer's responsibility."""
    line = _render(
        strategy,
        [
            Column(slot="left", value="ST"),
            # cell [10, 45): cursor ends at 45, leaving no room before "right".
            Column(slot="mid", value="MID", start_col=10, width=35, align="left"),
            Column(slot="right", value="99999"),
        ],
        width=48,
    )
    assert "MID" in line
    assert line.endswith(" 99999")  # min one space guaranteed before the right value


def test_left_right_pair_unaffected(strategy):
    """The common left+right pair path is unchanged by the mid-width addition."""
    line = _render(strategy, [Column(slot="left", value="合計"), Column(slot="right", value="278")])
    assert line.endswith("278")


# ---- full-width (Japanese) character handling ----


def test_cell_align_uses_display_width_for_japanese():
    """Padding is computed from display width (wcwidth), so the rendered cell is
    exactly ``width`` display columns wide regardless of full-width characters."""
    # "商品" display width 4 in a width-10 cell -> 6-space pad.
    assert AbstractReceiptData._render_mid_cell("商品", 10, "right") == "      商品"
    assert AbstractReceiptData._render_mid_cell("商品", 10, "left") == "商品      "
    assert AbstractReceiptData._render_mid_cell("商品", 10, "center") == "   商品   "
    for align in ("right", "left", "center"):
        cell = AbstractReceiptData._render_mid_cell("商品", 10, align)
        assert wcwidth.wcswidth(cell) == 10


def test_japanese_mid_cell_positioned_by_display_column():
    """A mid cell with full-width content lands at the right display columns even
    when the preceding left value itself contains wide characters."""
    strategy = _Strategy("default", 48)
    line = _render(
        strategy,
        [
            Column(slot="left", value="お茶 500ml"),  # wide chars before the cell
            Column(slot="mid", value="＠商品", start_col=14, width=10, align="right"),
            Column(slot="right", value="108外"),
        ],
    )
    # Cell occupies display columns [14, 24): value width 6 -> 4 leading spaces.
    cell = _disp_slice(line, 14, 24)
    assert cell == "    ＠商品"
    assert wcwidth.wcswidth(cell) == 10
    assert wcwidth.wcswidth(line) == 48


def test_mid_width_serialized_in_print_document():
    """`width` is emitted (camelCase) in the print document when set on a mid column."""
    element = ColumnsElement(
        columns=[
            Column(slot="left", value="お茶"),
            Column(slot="mid", value="@108", start_col=14, width=10, align="right"),
            Column(slot="right", value="108外"),
        ]
    )
    dumped = element.model_dump(by_alias=True, exclude_none=True)
    mid = next(c for c in dumped["columns"] if c["slot"] == "mid")
    assert mid["width"] == 10
    assert mid["startCol"] == 14
    assert mid["align"] == "right"

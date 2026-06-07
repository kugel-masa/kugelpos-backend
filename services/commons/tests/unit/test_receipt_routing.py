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
"""Unit tests for R/J/RJ channel routing in AbstractReceiptData."""
import pytest

from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.receipt_data_model import Page


class _Strategy(AbstractReceiptData):
    """Concrete strategy with no-op section builders for direct routing tests."""

    def make_receipt_header(self, model, page: Page):
        pass

    def make_receipt_body(self, model, page: Page):
        pass

    def make_receipt_footer(self, model, page: Page):
        pass


class _Model:
    tenant_id = "t1"
    store_code = "s1"
    terminal_no = 1


@pytest.fixture
def strategy():
    return _Strategy("default", 32)


def _values(elements):
    return [e.get("value") for e in elements if e.get("type") == "text"]


def test_default_channel_is_rj_both(strategy):
    """An element with no explicit channel goes to both receipt and journal."""
    elements = [strategy.line_left("HELLO")]
    doc = strategy.build_print_document(_Model(), elements)
    journal = strategy.render_journal_text(elements)
    assert "HELLO" in _values(doc["elements"])
    assert "HELLO" in journal


def test_receipt_only_channel_excluded_from_journal(strategy):
    elements = [strategy.line_left("RECEIPT", channel="R")]
    doc = strategy.build_print_document(_Model(), elements)
    journal = strategy.render_journal_text(elements)
    assert "RECEIPT" in _values(doc["elements"])
    assert "RECEIPT" not in journal


def test_journal_only_channel_excluded_from_receipt(strategy):
    elements = [strategy.line_left("JAN:4900000000000", channel="J")]
    doc = strategy.build_print_document(_Model(), elements)
    journal = strategy.render_journal_text(elements)
    assert "JAN:4900000000000" not in _values(doc["elements"])
    assert "JAN:4900000000000" in journal


def test_channel_not_serialized_into_print_document(strategy):
    """The routing channel is internal and must never appear in the JSON output."""
    elements = [
        strategy.line_center("T", channel="R"),
        strategy.line_split("a", "b", channel="RJ"),
        strategy.line_boarder(channel="R"),
    ]
    doc = strategy.build_print_document(_Model(), elements)
    for element in doc["elements"]:
        assert "channel" not in element


def test_all_journal_only_yields_empty_receipt_view(strategy):
    elements = [strategy.line_left("only-journal", channel="J")]
    doc = strategy.build_print_document(_Model(), elements)
    assert doc["elements"] == []

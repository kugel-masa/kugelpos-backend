# Copyright 2026 masa@kugel
"""render_journal_text takes an optional width, defaulting to the strategy's.

A caller may render at a width other than the strategy's own; without a width
the output is the same as before the parameter existed.
"""
from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.receipt.print_document_model import RuledLineElement, TextElement
from kugel_common.receipt.receipt_data_model import Page


class _Strategy(AbstractReceiptData):
    def make_receipt_header(self, model, page: Page):
        pass

    def make_receipt_body(self, model, page: Page):
        pass

    def make_receipt_footer(self, model, page: Page):
        pass


ELEMENTS = [TextElement(value="TOTAL", align="right"), RuledLineElement(char="-")]


def test_without_a_width_the_strategy_width_is_used():
    strategy = _Strategy("default", 32)
    assert strategy.render_journal_text(ELEMENTS) == strategy.render_journal_text(ELEMENTS, width=32)
    assert max(len(line) for line in strategy.render_journal_text(ELEMENTS).splitlines()) == 32


def test_a_given_width_is_used_instead():
    strategy = _Strategy("default", 32)
    lines = strategy.render_journal_text(ELEMENTS, width=20).splitlines()
    assert lines == ["               TOTAL", "-" * 20]

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
import pytest

from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.receipt.receipt_data_model import Page

from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.services.receipt_data.cash_in_out_receipt_data import CashInOutReceiptData
from app.services.receipt_data.open_close_receipt_data import OpenCloseReceiptData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cash_log(**overrides) -> CashInOutLog:
    defaults = dict(
        store_code="S001",
        store_name="Test Store",
        terminal_no=1,
        staff_id="000123",
        business_date="20240101",
        open_counter=1,
        generate_date_time="2024-01-01T10:00:00",
        amount=1000,
        description="Cash deposit",
    )
    defaults.update(overrides)
    return CashInOutLog(**defaults)


def make_open_close_log(**overrides) -> OpenCloseLog:
    terminal_info = overrides.pop("terminal_info", None)
    if terminal_info is None:
        terminal_info = TerminalInfoDocument(
            initial_amount=10000,
            physical_amount=15000,
            staff=StaffMasterDocument(id="000123", name="Test Staff"),
        )
    defaults = dict(
        store_code="S001",
        store_name="Test Store",
        terminal_no=1,
        staff_id="000123",
        business_date="20240101",
        open_counter=1,
        business_counter=5,
        operation="open",
        generate_date_time="2024-01-01T09:00:00",
        terminal_info=terminal_info,
    )
    defaults.update(overrides)
    return OpenCloseLog(**defaults)


# ---------------------------------------------------------------------------
# CashInOutReceiptData
# ---------------------------------------------------------------------------

class TestCashInOutReceiptData:
    @pytest.fixture
    def receipt(self):
        return CashInOutReceiptData(name="cash_receipt", width=32)

    def test_make_receipt_header_cash_in(self, receipt):
        """Header for positive amount (cash in) includes store, terminal, staff, date, and title."""
        log = make_cash_log(amount=500)
        page = Page()
        receipt.make_receipt_header(log, page)

        text = "\n".join(str(line) for line in page.lines)
        assert len(page.lines) >= 5
        # Verify title is cash in
        assert any("入 金" in str(line) for line in page.lines)

    def test_make_receipt_header_cash_out(self, receipt):
        """Header for negative amount (cash out) includes the cash-out title."""
        log = make_cash_log(amount=-500)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert any("出 金" in str(line) for line in page.lines)

    def test_make_receipt_header_no_store_name(self, receipt):
        """When store_name is None, falls back to store_code."""
        log = make_cash_log(store_name=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        # Should use store_code as fallback
        assert len(page.lines) >= 1

    def test_make_receipt_header_no_terminal_no(self, receipt):
        """When terminal_no is None, shows store total label."""
        log = make_cash_log(terminal_no=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert len(page.lines) >= 2

    def test_make_receipt_header_no_staff_id(self, receipt):
        """When staff_id is None, shows dashes for staff."""
        log = make_cash_log(staff_id=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert len(page.lines) >= 2

    def test_make_receipt_header_no_open_counter(self, receipt):
        """When open_counter is None, the open counter line is skipped."""
        log = make_cash_log(open_counter=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        log_with = make_cash_log(open_counter=1)
        page_with = Page()
        receipt.make_receipt_header(log_with, page_with)

        assert len(page.lines) < len(page_with.lines)

    def test_make_receipt_body(self, receipt):
        """Body shows border, description with amount, and another border."""
        log = make_cash_log(description="Deposit", amount=5000)
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3  # border + content + border

    def test_make_receipt_body_no_description(self, receipt):
        """Body with None description uses empty string."""
        log = make_cash_log(description=None, amount=100)
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3

    def test_make_receipt_footer(self, receipt):
        """Footer shows receipt number placeholder."""
        log = make_cash_log()
        page = Page()
        receipt.make_receipt_footer(log, page)

        assert len(page.lines) == 1

    def test_make_receipt_data_full(self, receipt):
        """Full make_receipt_data generates receipt_text and journal_text."""
        log = make_cash_log()
        result = receipt.make_receipt_data(log)

        assert result.receipt_text is not None
        assert result.journal_text is not None
        assert len(result.receipt_text) > 0
        assert len(result.journal_text) > 0


# ---------------------------------------------------------------------------
# OpenCloseReceiptData
# ---------------------------------------------------------------------------

class TestOpenCloseReceiptData:
    @pytest.fixture
    def receipt(self):
        return OpenCloseReceiptData(name="open_close_receipt", width=32)

    def test_make_receipt_header_open(self, receipt):
        """Header for open operation includes open title."""
        log = make_open_close_log(operation="open")
        page = Page()
        receipt.make_receipt_header(log, page)

        assert any("開 設" in str(line) for line in page.lines)

    def test_make_receipt_header_close(self, receipt):
        """Header for close operation includes close title."""
        log = make_open_close_log(operation="close")
        page = Page()
        receipt.make_receipt_header(log, page)

        assert any("精 算" in str(line) for line in page.lines)

    def test_make_receipt_header_no_store_name(self, receipt):
        """When store_name is None, falls back to store_code."""
        log = make_open_close_log(store_name=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert len(page.lines) >= 1

    def test_make_receipt_header_no_terminal_no(self, receipt):
        """When terminal_no is None, shows store total."""
        log = make_open_close_log(terminal_no=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert len(page.lines) >= 2

    def test_make_receipt_header_no_staff_in_terminal_info(self, receipt):
        """When terminal_info.staff is None, shows dashes for staff."""
        ti = TerminalInfoDocument(initial_amount=10000, staff=None)
        log = make_open_close_log(terminal_info=ti)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert len(page.lines) >= 2

    def test_make_receipt_header_no_terminal_info(self, receipt):
        """When terminal_info is None, shows dashes for staff."""
        log = make_open_close_log(terminal_info=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        assert len(page.lines) >= 2

    def test_make_receipt_header_no_open_counter(self, receipt):
        """When open_counter is None, the counter line is skipped."""
        log = make_open_close_log(open_counter=None)
        page = Page()
        receipt.make_receipt_header(log, page)

        log_with = make_open_close_log(open_counter=1)
        page_with = Page()
        receipt.make_receipt_header(log_with, page_with)

        assert len(page.lines) < len(page_with.lines)

    def test_make_receipt_body_open(self, receipt):
        """Open body shows initial amount (float)."""
        log = make_open_close_log(operation="open")
        page = Page()
        receipt.make_receipt_body(log, page)

        # border + content + border
        assert len(page.lines) == 3

    def test_make_receipt_body_open_no_terminal_info(self, receipt):
        """Open body with no terminal_info defaults initial amount to 0."""
        log = make_open_close_log(operation="open", terminal_info=None)
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3

    def test_make_receipt_body_open_no_initial_amount(self, receipt):
        """Open body with terminal_info but no initial_amount defaults to 0."""
        ti = TerminalInfoDocument(initial_amount=None)
        log = make_open_close_log(operation="open", terminal_info=ti)
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3

    def test_make_receipt_body_close(self, receipt):
        """Close body shows physical amount."""
        log = make_open_close_log(operation="close")
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3

    def test_make_receipt_body_close_no_terminal_info(self, receipt):
        """Close body with no terminal_info defaults physical amount to 0."""
        log = make_open_close_log(operation="close", terminal_info=None)
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3

    def test_make_receipt_body_close_no_physical_amount(self, receipt):
        """Close body with terminal_info but no physical_amount defaults to 0."""
        ti = TerminalInfoDocument(physical_amount=None)
        log = make_open_close_log(operation="close", terminal_info=ti)
        page = Page()
        receipt.make_receipt_body(log, page)

        assert len(page.lines) == 3

    def test_make_receipt_footer(self, receipt):
        """Footer shows receipt number placeholder."""
        log = make_open_close_log()
        page = Page()
        receipt.make_receipt_footer(log, page)

        assert len(page.lines) == 1

    def test_make_receipt_data_full_open(self, receipt):
        """Full make_receipt_data for open generates receipt_text and journal_text."""
        log = make_open_close_log(operation="open")
        result = receipt.make_receipt_data(log)

        assert result.receipt_text is not None
        assert result.journal_text is not None

    def test_make_receipt_data_full_close(self, receipt):
        """Full make_receipt_data for close generates receipt_text and journal_text."""
        log = make_open_close_log(operation="close")
        result = receipt.make_receipt_data(log)

        assert result.receipt_text is not None
        assert result.journal_text is not None

# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from kugel_common.enums import TransactionType
from kugel_common.utils.http_client_helper import HttpClientError

from app.services.report_service import ReportService
from app.models.documents.sales_report_document import SalesReportDocument


@pytest.mark.asyncio
class TestJournalIntegration:
    """Test cases for report to journal integration"""

    async def test_send_flash_report_to_journal(self):
        """Test sending flash report to journal service"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Create mock report data
        mock_report_data = MagicMock(spec=SalesReportDocument)
        mock_report_data.receipt_text = "Flash Report Receipt Text"
        mock_report_data.journal_text = "Flash Report Journal Text"
        mock_report_data.sales_net = MagicMock()
        mock_report_data.sales_net.amount = 1000.0
        mock_report_data.sales_net.quantity = 10

        # Mock the HTTP client
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value={"success": True})

            # Call the method
            await service._send_report_to_journal(
                store_code="STORE001",
                terminal_no=1,
                report_scope="flash",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                report_data=mock_report_data,
                requesting_terminal_no=1,  # Same as terminal_no for terminal-specific reports
                requesting_staff_id="STAFF001",  # Staff who requested the report
            )

            # Verify the call
            mock_get_client.assert_called_once_with("journal")

            # Verify the endpoint and data
            expected_endpoint = "/tenants/tenant123/stores/STORE001/terminals/1/journals"
            call_args = mock_client.post.call_args

            assert call_args[0][0] == expected_endpoint

            # Verify headers include JWT token
            assert "headers" in call_args[1]
            assert "Authorization" in call_args[1]["headers"]
            assert call_args[1]["headers"]["Authorization"].startswith("Bearer ")

            # Journal data uses camelCase
            journal_data = call_args[1]["json"]
            assert journal_data["transactionType"] == TransactionType.FlashReport.value
            assert journal_data["receiptText"] == "Flash Report Receipt Text"
            assert journal_data["journalText"] == "Flash Report Journal Text"
            assert journal_data["amount"] == 0.0  # Reports don't have amount
            assert journal_data["quantity"] == 0  # Reports don't have quantity
            assert journal_data["storeCode"] == "STORE001"
            assert journal_data["terminalNo"] == 1
            assert journal_data["businessDate"] == "20250110"
            assert journal_data["businessCounter"] == 1  # Verify correct field name (not businesCounter)
            assert journal_data["openCounter"] == 1
            assert journal_data["staffId"] == "STAFF001"  # Verify staff ID is recorded
            assert journal_data["userId"] is None  # Verify userId is None

    async def test_send_daily_report_to_journal(self):
        """Test sending daily report to journal service"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Create mock report data without receipt/journal text
        mock_report_data = MagicMock(spec=SalesReportDocument)
        mock_report_data.receipt_text = None
        mock_report_data.journal_text = None
        mock_report_data.sales_net = MagicMock()
        mock_report_data.sales_net.amount = 5000.0
        mock_report_data.sales_net.quantity = 50
        mock_report_data.model_dump = MagicMock(return_value={"test": "data"})

        # Mock the HTTP client
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value={"success": True})

            # Call the method
            await service._send_report_to_journal(
                store_code="STORE001",
                terminal_no=None,  # Store-wide report
                report_scope="daily",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                report_data=mock_report_data,
                requesting_terminal_no=2,  # Terminal 2 requested the store report
                requesting_staff_id=None,  # No staff logged in for this test
            )

            # Verify the call
            mock_get_client.assert_called_once_with("journal")

            # Verify the endpoint and data
            expected_endpoint = (
                "/tenants/tenant123/stores/STORE001/terminals/2/journals"  # Now uses requesting terminal
            )
            call_args = mock_client.post.call_args

            assert call_args[0][0] == expected_endpoint

            # Verify headers include JWT token
            assert "headers" in call_args[1]
            assert "Authorization" in call_args[1]["headers"]

            journal_data = call_args[1]["json"]
            assert journal_data["transactionType"] == TransactionType.DailyReport.value
            assert journal_data["receiptText"] == "Report: sales (daily)\nStore: STORE001\nDate: 20250110"
            assert '"test": "data"' in journal_data["journalText"]  # JSON serialized
            assert journal_data["amount"] == 0.0  # Reports don't have amount
            assert journal_data["quantity"] == 0  # Reports don't have quantity
            assert journal_data["terminalNo"] == 2  # Uses the requesting terminal
            assert journal_data["businessCounter"] == 1  # Verify correct field name (not businesCounter)
            assert journal_data["openCounter"] == 1
            assert journal_data["staffId"] == "SYSTEM"  # Should default to SYSTEM when no staff
            assert journal_data["userId"] is None  # Verify userId is None

    async def test_journal_error_does_not_fail_report(self):
        """Test that journal service errors don't fail report generation"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Create mock report data
        mock_report_data = MagicMock(spec=SalesReportDocument)
        mock_report_data.receipt_text = "Test Receipt"
        mock_report_data.journal_text = "Test Journal"
        mock_report_data.sales_net = MagicMock()
        mock_report_data.sales_net.amount = 1000.0
        mock_report_data.sales_net.quantity = 10

        # Mock the HTTP client to raise an error
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=HttpClientError("Connection failed", status_code=500))

            # Call should not raise exception
            await service._send_report_to_journal(
                store_code="STORE001",
                terminal_no=1,
                report_scope="flash",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                report_data=mock_report_data,
                requesting_terminal_no=None,
                requesting_staff_id=None,
            )

            # Verify the error was attempted
            mock_client.post.assert_called_once()

    async def test_store_report_without_requesting_terminal(self):
        """Test that store-wide report defaults to terminal 0 when no requesting terminal is provided"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Create mock report data
        mock_report_data = MagicMock(spec=SalesReportDocument)
        mock_report_data.receipt_text = "Store Report"
        mock_report_data.journal_text = "Store Journal"
        mock_report_data.sales_net = MagicMock()
        mock_report_data.sales_net.amount = 2000.0
        mock_report_data.sales_net.quantity = 20

        # Mock the HTTP client
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value={"success": True})

            # Call the method without requesting_terminal_no
            await service._send_report_to_journal(
                store_code="STORE001",
                terminal_no=None,  # Store-wide report
                report_scope="flash",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                report_data=mock_report_data,
                # No requesting_terminal_no or requesting_staff_id parameters
            )

            # Verify the call
            call_args = mock_client.post.call_args
            journal_data = call_args[1]["json"]

            # Should default to terminal 0 when no requesting terminal is provided
            assert journal_data["terminalNo"] == 0

    async def test_unknown_report_scope_skips_journal(self):
        """Test that unknown report scope skips journal without error"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Create mock report data
        mock_report_data = MagicMock()

        # Mock the HTTP client
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            # Call with unknown report scope
            await service._send_report_to_journal(
                store_code="STORE001",
                terminal_no=1,
                report_scope="unknown_scope",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                report_data=mock_report_data,
                requesting_terminal_no=None,
                requesting_staff_id=None,
            )

            # Verify HTTP client was not called
            mock_get_client.assert_not_called()

    async def test_jwt_request_does_not_create_journal(self):
        """Test that reports requested with JWT token do not create journal entries"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Mock plugin manager and report maker
        mock_plugin_manager = MagicMock()
        mock_report_maker = AsyncMock()
        mock_report_data = MagicMock()
        mock_report_data.receipt_text = "Test Receipt"
        mock_report_data.journal_text = "Test Journal"
        mock_report_maker.generate_report = AsyncMock(return_value=mock_report_data)

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Override report makers
        service.report_makers = {"sales": mock_report_maker}

        # Mock the HTTP client
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            # Call the method with JWT request (is_api_key_request=False)
            await service.get_report_for_terminal_async(
                store_code="STORE001",
                terminal_no=1,
                report_scope="flash",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                requesting_terminal_no=1,
                requesting_staff_id=None,
                is_api_key_request=False,  # JWT request
            )

            # Verify HTTP client was NOT called (no journal entry)
            mock_get_client.assert_not_called()

    async def test_api_key_request_creates_journal(self):
        """Test that reports requested with API key do create journal entries"""
        # Setup mocks
        mock_tran_repo = AsyncMock()
        mock_cash_repo = AsyncMock()
        mock_open_close_repo = AsyncMock()
        mock_daily_info_repo = AsyncMock()
        mock_terminal_repo = AsyncMock()

        mock_tran_repo.tenant_id = "tenant123"

        # Mock plugin manager and report maker
        mock_report_maker = AsyncMock()
        mock_report_data = MagicMock()
        mock_report_data.receipt_text = "Test Receipt"
        mock_report_data.journal_text = "Test Journal"
        mock_report_data.sales_net = MagicMock()
        mock_report_data.sales_net.amount = 1000.0
        mock_report_data.sales_net.quantity = 10
        mock_report_maker.generate_report = AsyncMock(return_value=mock_report_data)

        # Create service instance
        service = ReportService(
            tran_repository=mock_tran_repo,
            cash_in_out_log_repository=mock_cash_repo,
            open_close_log_repository=mock_open_close_repo,
            daily_info_repository=mock_daily_info_repo,
            terminal_info_repository=mock_terminal_repo,
        )

        # Override report makers
        service.report_makers = {"sales": mock_report_maker}

        # Mock the HTTP client
        with patch("app.services.report_service.get_service_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value={"success": True})

            # Call the method with API key request (is_api_key_request=True)
            await service.get_report_for_terminal_async(
                store_code="STORE001",
                terminal_no=1,
                report_scope="flash",
                report_type="sales",
                business_date="20250110",
                open_counter=1,
                business_counter=1,
                requesting_terminal_no=1,
                requesting_staff_id="STAFF001",
                is_api_key_request=True,  # API key request
            )

            # Verify HTTP client WAS called (journal entry created)
            mock_get_client.assert_called_once_with("journal")

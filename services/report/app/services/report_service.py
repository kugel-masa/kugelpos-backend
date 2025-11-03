# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.  # report_service.py
from typing import Any
from collections import defaultdict
from logging import getLogger

logger = getLogger(__name__)

from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.exceptions import ServiceException, CannotCreateException
from kugel_common.utils.misc import get_app_time_str
from kugel_common.utils.http_client_helper import get_service_client, HttpClientError
from kugel_common.utils.service_auth import create_service_token
from kugel_common.enums import TransactionType

from app.models.repositories.terminal_info_web_repository import TerminalInfoWebRepository
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.daily_info_document_repository import DailyInfoDocumentRepository
from app.models.documents.daily_info_document import DailyInfoDocument
from app.services.report_plugin_manager import ReportPluginManager
from app.exceptions import (
    ReportNotFoundException,
    ReportValidationException,
    ReportGenerationException,
    ReportTypeException,
    ReportScopeException,
    ReportDateException,
    ReportDataException,
    TerminalNotClosedException,
    LogsMissingException,
    LogCountMismatchException,
    TransactionMissingException,
    CashInOutMissingException,
    OpenCloseLogMissingException,
    VerificationFailedException,
    DailyInfoException,
)


class ReportService:
    """
    Service for generating various types of business reports.

    This service is responsible for generating reports based on transaction logs,
    cash operations, and terminal open/close events. It uses a plugin architecture
    to support different report types, and includes verification mechanisms to ensure
    data completeness and consistency before generating daily reports.
    """

    def __init__(
        self,
        tran_repository: TranlogRepository,
        cash_in_out_log_repository: CashInOutLogRepository,
        open_close_log_repository: OpenCloseLogRepository,
        daily_info_repository: DailyInfoDocumentRepository,
        terminal_info_repository: TerminalInfoWebRepository,
    ):
        """
        Initialize the ReportService with required repositories.

        Args:
            tran_repository: Repository for transaction logs
            cash_in_out_log_repository: Repository for cash in/out operation logs
            open_close_log_repository: Repository for terminal open/close logs
            daily_info_repository: Repository for daily information documents
            terminal_info_repository: Repository for terminal information
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        self.daily_info_repository = daily_info_repository
        self.terminal_repository = terminal_info_repository
        self.tenant_id = self.tran_repository.tenant_id
        self.plugin_manager = ReportPluginManager()
        self.report_makers = self.plugin_manager.load_plugins(
            "report_makers",
            tran_repository=self.tran_repository,
            cash_in_out_log_repository=self.cash_in_out_log_repository,
            open_close_log_repository=self.open_close_log_repository,
        )

    async def get_report_for_store_async(
        self,
        store_code: str,
        report_scope: str,
        report_type: str,
        business_date: str = None,
        open_counter: int = None,
        business_counter: int = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
        requesting_terminal_no: int = None,
        requesting_staff_id: str = None,
        is_api_key_request: bool = False,
        business_date_from: str = None,
        business_date_to: str = None,
    ):
        """
        Generate a report for an entire store.

        This method verifies that all terminals in the store are closed (for daily reports)
        before generating the requested report. It uses the appropriate report plugin
        based on the report_type parameter.

        Args:
            store_code: Identifier for the store
            report_scope: Scope of the report (e.g., 'flash', 'daily')
            report_type: Type of report to generate (must correspond to a loaded plugin)
            business_date: Date for which the report is generated (single date mode)
            open_counter: Optional counter for terminal open/close cycles
            business_counter: Optional business counter for the day
            limit: Maximum number of records to include
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction
            requesting_terminal_no: Terminal number that requested the report (for journal tracking)
            requesting_staff_id: Staff ID who requested the report (for journal tracking)
            is_api_key_request: Whether this request came from API key authentication (determines if journal entry is created)
            business_date_from: Start date for date range mode (optional)
            business_date_to: End date for date range mode (optional)

        Returns:
            The generated report data

        Raises:
            TerminalNotClosedException: If any terminal in the store is not closed (single date mode only)
            ReportGenerationException: If an error occurs during report generation
            ReportNotFoundException: If the requested report type does not exist
        """
        logger.debug(
            f"get_report_for_store_async: {store_code}, {report_scope}, {report_type}, {business_date}, {open_counter}, {limit}, {page}, {sort}"
        )

        # Normalize report_scope: treat "flush" as "flash" for backward compatibility
        if report_scope == "flush":
            report_scope = "flash"

        # check if conditions are met for daily report
        # Skip terminal closed check if date range is specified
        if report_scope == "daily" and not (business_date_from and business_date_to):
            # check if all terminals in the store are closed (single date mode only)
            try:
                await self._check_if_terminal_closed(
                    store_code=store_code, business_date=business_date, open_counter=open_counter
                )
            except ServiceException as e:
                message = f"check_if_terminal_closed->false. store_code->{store_code}, business_date->{business_date}, open_counter->{open_counter}"
                raise TerminalNotClosedException(message, logger, e) from e

        if report_type in self.report_makers:
            try:
                maker = self.report_makers[report_type]
                
                # Check if the maker supports date range parameters
                if hasattr(maker.generate_report, '__code__') and 'business_date_from' in maker.generate_report.__code__.co_varnames:
                    # Maker supports date range parameters
                    report_data = await maker.generate_report(
                        store_code=store_code,
                        terminal_no=None,
                        business_counter=business_counter,
                        business_date=business_date,
                        open_counter=open_counter,
                        report_scope=report_scope,
                        report_type=report_type,
                        limit=limit,
                        page=page,
                        sort=sort,
                        business_date_from=business_date_from,
                        business_date_to=business_date_to,
                    )
                else:
                    # Maker doesn't support date range parameters (legacy)
                    report_data = await maker.generate_report(
                        store_code=store_code,
                        terminal_no=None,
                        business_counter=business_counter,
                        business_date=business_date,
                        open_counter=open_counter,
                        report_scope=report_scope,
                        report_type=report_type,
                        limit=limit,
                        page=page,
                        sort=sort,
                    )

                # Send report to journal service only for API key requests
                if is_api_key_request:
                    logger.info("API key request detected for store report, sending to journal")
                    # For date range reports, use business_date_from as the business_date for journal
                    journal_business_date = business_date if business_date else business_date_from
                    await self._send_report_to_journal(
                        store_code=store_code,
                        terminal_no=None,
                        report_scope=report_scope,
                        report_type=report_type,
                        business_date=journal_business_date,
                        open_counter=open_counter,
                        business_counter=business_counter,
                        report_data=report_data,
                        requesting_terminal_no=requesting_terminal_no,
                        requesting_staff_id=requesting_staff_id,
                    )

                return report_data
            except Exception as e:
                import traceback
                logger.error(f"Detailed error in report generation: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                if business_date_from and business_date_to:
                    message = f"Error occurred during report generation: report_type->{report_type}, store_code->{store_code}, date_range->{business_date_from} to {business_date_to}"
                else:
                    message = f"Error occurred during report generation: report_type->{report_type}, store_code->{store_code}, business_date->{business_date}"
                raise ReportGenerationException(message, logger, e) from e
        else:
            message = f"Invalid report type: {report_type}"
            raise ReportNotFoundException(message, logger)

    async def get_report_for_terminal_async(
        self,
        store_code: str,
        terminal_no: int,
        report_scope: str,
        report_type: str,
        business_date: str = None,
        open_counter: int = None,
        business_counter: int = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
        requesting_staff_id: str = None,
        requesting_terminal_no: int = None,
        is_api_key_request: bool = False,
        business_date_from: str = None,
        business_date_to: str = None,
    ):
        """
        Generate a report for a specific terminal.

        This method verifies that the specified terminal is closed (for daily reports)
        before generating the requested report. It uses the appropriate report plugin
        based on the report_type parameter.

        Args:
            store_code: Identifier for the store
            terminal_no: Terminal number
            report_scope: Scope of the report (e.g., 'flash', 'daily')
            report_type: Type of report to generate (must correspond to a loaded plugin)
            business_date: Date for which the report is generated
            open_counter: Optional counter for terminal open/close cycles
            business_counter: Optional business counter for the day
            limit: Maximum number of records to include
            page: Page number for pagination
            sort: List of tuples containing field name and sort direction
            requesting_staff_id: Staff ID who requested the report (for journal tracking)
            requesting_terminal_no: Terminal number that requested the report (for journal tracking)
            is_api_key_request: Whether this request came from API key authentication (determines if journal entry is created)

        Returns:
            The generated report data

        Raises:
            TerminalNotClosedException: If the terminal is not closed
            ReportGenerationException: If an error occurs during report generation
            ReportNotFoundException: If the requested report type does not exist
        """
        logger.debug(
            f"get_report_for_terminal_async: {store_code}, {terminal_no}, {report_scope}, {report_type}, {business_date}, {open_counter}, {limit}, {page}, {sort}"
        )

        # Normalize report_scope: treat "flush" as "flash" for backward compatibility
        if report_scope == "flush":
            report_scope = "flash"

        # check if conditions are met for daily report
        # Skip terminal closed check if date range is specified
        if report_scope == "daily" and not (business_date_from and business_date_to):
            # check if all transactions are received for the business date and open counter (single date mode only)
            try:
                await self._check_if_terminal_closed(
                    store_code=store_code,
                    business_date=business_date,
                    open_counter=open_counter,
                    terminal_no=terminal_no,
                )
            except ServiceException as e:
                message = f"check_if_terminal_closed->false. store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
                raise TerminalNotClosedException(message, logger, e) from e

        if report_type in self.report_makers:
            try:
                maker = self.report_makers[report_type]
                
                # Check if the maker supports date range parameters
                if hasattr(maker.generate_report, '__code__') and 'business_date_from' in maker.generate_report.__code__.co_varnames:
                    # Maker supports date range parameters
                    report_data = await maker.generate_report(
                        store_code=store_code,
                        terminal_no=terminal_no,
                        report_scope=report_scope,
                        report_type=report_type,
                        business_date=business_date,
                        open_counter=open_counter,
                        business_counter=business_counter,
                        limit=limit,
                        page=page,
                        sort=sort,
                        business_date_from=business_date_from,
                        business_date_to=business_date_to,
                    )
                else:
                    # Maker doesn't support date range parameters (legacy)
                    report_data = await maker.generate_report(
                        store_code=store_code,
                        terminal_no=terminal_no,
                        report_scope=report_scope,
                        report_type=report_type,
                        business_date=business_date,
                        open_counter=open_counter,
                        business_counter=business_counter,
                        limit=limit,
                        page=page,
                        sort=sort,
                    )

                # Send report to journal service only for API key requests
                if is_api_key_request:
                    logger.info("API key request detected for terminal report, sending to journal")
                    # For date range reports, use business_date_from as the business_date for journal
                    journal_business_date = business_date if business_date else business_date_from
                    await self._send_report_to_journal(
                        store_code=store_code,
                        terminal_no=terminal_no,
                        report_scope=report_scope,
                        report_type=report_type,
                        business_date=journal_business_date,
                        open_counter=open_counter,
                        business_counter=business_counter,
                        report_data=report_data,
                        requesting_staff_id=requesting_staff_id,
                        requesting_terminal_no=requesting_terminal_no,
                    )

                return report_data
            except Exception as e:
                if business_date_from and business_date_to:
                    message = f"Error occurred during report generation: report_type->{report_type}, store_code->{store_code}, terminal_no->{terminal_no}, date_range->{business_date_from} to {business_date_to}"
                else:
                    message = f"Error occurred during report generation: report_type->{report_type}, store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}"
                raise ReportGenerationException(message, logger, e) from e
        else:
            message = f"Invalid report type: {report_type}"
            raise ReportNotFoundException(message, logger)

    async def _create_daily_info(self, daily_info: DailyInfoDocument, verified: bool, verified_message: str):
        """
        Create or update a daily information document with verification status.

        Args:
            daily_info: The daily information document to create/update
            verified: Boolean indicating if the terminal data is verified
            verified_message: Message describing the verification status

        Raises:
            CannotCreateException: If the daily info document cannot be created
        """
        try:
            daily_info.verified = verified
            daily_info.verified_message = verified_message
            daily_info.verified_update_time = get_app_time_str()
            await self.daily_info_repository.create_daily_info_document(daily_info)
        except Exception as e:
            message = f"Cannot create daily info document: {daily_info}"
            raise CannotCreateException(
                message, self.daily_info_repository.collection_name, daily_info, logger, e
            ) from e

    async def _check_if_terminal_closed(
        self, store_code: str, business_date: str, open_counter: int, terminal_no: int = None
    ) -> None:
        """
        Verify if specified terminal(s) are properly closed and all logs are present.

        This method checks if a specific terminal or all terminals in a store are
        properly closed and if all required logs (transactions, cash operations) have been
        correctly recorded for the business date and open counter.

        Args:
            store_code: Identifier for the store
            business_date: Date to check for terminal closure
            open_counter: Counter for terminal open/close cycles
            terminal_no: Specific terminal to check, or None for all terminals

        Raises:
            ServiceException: If terminal verification fails
        """
        try:
            if terminal_no:
                await self._commit_terminal_report_async(
                    tenant_id=self.tenant_id,
                    store_code=store_code,
                    terminal_no=terminal_no,
                    business_date=business_date,
                    open_counter=open_counter,
                )
            else:
                await self._commit_store_report_async(
                    store_code=store_code, business_date=business_date, open_counter=open_counter
                )

        except ServiceException as e:
            # terminal is not verified
            message = f"Terminal verification failed. tenant_id->{self.tenant_id}, store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
            raise ServiceException(message, logger, e) from e

        # terminal is verified
        logger.info(
            f"Terminal verification successful. tenant_id->{self.tenant_id}, store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
        )

    async def _commit_store_report_async(self, store_code: str, business_date: str, open_counter: int) -> None:
        """
        Verify all terminals in a store for report generation.

        This method attempts to verify each terminal in the store to ensure all
        are properly closed and have complete logs for the specified business date
        and open counter.

        Args:
            store_code: Identifier for the store
            business_date: Date to verify terminal data for
            open_counter: Counter for terminal open/close cycles

        Raises:
            ServiceException: If any terminal in the store fails verification
        """
        logger.debug(f"commit_store_report_async: {store_code}, {business_date}, {open_counter}")

        # get all terminals for the store
        all_verified = True
        terminals = await self.terminal_repository.get_terminal_info_list_async()
        for terminal in terminals:
            try:
                await self._commit_terminal_report_async(
                    tenant_id=self.tenant_id,
                    store_code=store_code,
                    terminal_no=terminal.terminal_no,
                    business_date=business_date,
                    open_counter=open_counter,
                )
            except ServiceException as e:
                message = f"Cannot verify terminal. tenant_id->{self.tenant_id}, store_code->{store_code}, terminal_no->{terminal.terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
                logger.info(message)
                all_verified = False

        if not all_verified:
            message = f"Cannot verify some terminals in store. tenant_id->{self.tenant_id}, store_code->{store_code}, business_date->{business_date}, open_counter->{open_counter}"
            raise ServiceException(message, logger)

        logger.info(
            f"All terminals are verified. tenant_id->{self.tenant_id}, store_code->{store_code}, business_date->{business_date}, open_counter->{open_counter}"
        )

    async def _commit_terminal_report_async(
        self, tenant_id: str, store_code: str, terminal_no: int, business_date: str, open_counter: int
    ) -> None:
        """
        Verify a specific terminal for report generation.

        This method checks if a terminal is properly closed and has complete logs
        for the specified business date and open counter. It verifies:
        1. The existence of open/close logs
        2. The count of cash in/out operations matches the expected count
        3. The count of transactions matches the expected count

        If verification passes, a daily info document is created with verified=True.

        Args:
            tenant_id: Tenant identifier
            store_code: Identifier for the store
            terminal_no: Terminal number to verify
            business_date: Date to verify terminal data for
            open_counter: Counter for terminal open/close cycles

        Raises:
            OpenCloseLogMissingException: If close logs are missing
            CashInOutMissingException: If cash operation logs are missing or inconsistent
            TransactionMissingException: If transaction logs are missing or inconsistent
        """
        logger.debug(f"commit_report_async: {tenant_id}, {store_code}, {terminal_no}, {business_date}, {open_counter}")

        # get daily info document
        daily_info = await self.daily_info_repository.get_daily_info_documents(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            limit=0,
            page=1,
        )
        if daily_info.metadata.total > 0:
            if daily_info.data[0].verified:
                logger.debug(
                    f"Terminal is already verified. tenant_id->{tenant_id}, store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
                )
                return

        # create daily info document
        daily_info = DailyInfoDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            verified=None,
            verified_update_time=None,
            verified_message=None,
        )

        # get open log
        open_log = await self.open_close_log_repository.get_open_close_logs(
            store_code=store_code,
            business_date=business_date,
            terminal_no=terminal_no,
            open_counter=open_counter,
            operation="open",
            limit=1,
            page=1,
            sort=[("generate_date_time", -1)],
        )
        if open_log.metadata.total == 0:
            message = f"Terminal not opened. tenant_id->{tenant_id}, store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
            logger.debug(message)
            # not opened yet
            return

        # get close log
        open_close_logs = await self.open_close_log_repository.get_open_close_logs(
            store_code=store_code,
            business_date=business_date,
            terminal_no=terminal_no,
            open_counter=open_counter,
            operation="close",
            limit=1,
            page=1,
            sort=[("generate_date_time", -1)],
        )
        if open_close_logs.metadata.total == 0:
            message = f"No close logs found for the given business date and open counter. store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
            await self._create_daily_info(daily_info, False, message)
            raise OpenCloseLogMissingException(message, logger)

        # set values from open close logs
        cash_log_count = open_close_logs.data[0].cash_in_out_count
        cash_log_datetime = open_close_logs.data[0].cash_in_out_last_datetime
        tran_log_count = open_close_logs.data[0].cart_transaction_count
        tran_log_no = open_close_logs.data[0].cart_transaction_last_no

        # get cash in/out logs
        filter = {
            "store_code": store_code,
            "business_date": business_date,
            "terminal_no": terminal_no,
            "open_counter": open_counter,
        }
        cash_in_out_logs = await self.cash_in_out_log_repository.get_cash_in_out_logs(
            filter=filter, limit=1, page=1, sort=[("generate_date_time", -1)]
        )
        # check if cash in/out logs are received
        if cash_in_out_logs.metadata.total != cash_log_count:
            message = f"Missing cash in/out logs. Expected count->{cash_log_count}, Actual count->{cash_in_out_logs.metadata.total}"
            await self._create_daily_info(daily_info, False, message)
            raise CashInOutMissingException(message, logger)
        if len(cash_in_out_logs.data) != 0:
            if cash_in_out_logs.data[0].generate_date_time != cash_log_datetime:
                message = f"Missing cash in/out logs. Expected datetime->{cash_log_datetime}, Actual datetime->{cash_in_out_logs.data[0].generate_date_time}"
                await self._create_daily_info(daily_info, False, message)
                raise CashInOutMissingException(message, logger)
        logger.info(
            f"all cash in/out logs are received for the business date and open counter. store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
        )

        # get tran logs
        tran_logs = await self.tran_repository.get_tranlog_list_by_query_async(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            limit=1,
            page=1,
            sort=[("generate_date_time", -1)],
            include_cancelled=True,
        )
        # check if transaction logs are received
        if tran_logs.metadata.total != tran_log_count:
            message = (
                f"Missing transaction logs. Expected count->{tran_log_count}, Actual count->{tran_logs.metadata.total}"
            )
            await self._create_daily_info(daily_info, False, message)
            raise TransactionMissingException(message, logger)
        if len(tran_logs.data) != 0:
            if tran_logs.data[0].transaction_no != tran_log_no:
                message = f"Missing transaction logs. Expected transaction no->{tran_log_no}, Actual transaction no->{tran_logs.data[0].transaction_no}"
                await self._create_daily_info(daily_info, False, message)
                raise TransactionMissingException(message, logger)
        logger.info(
            f"all transaction logs are received for the business date and open counter. store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}, open_counter->{open_counter}"
        )

        # create daily info document
        await self._create_daily_info(daily_info, True, "All logs are received successfully")

    async def _send_report_to_journal(
        self,
        store_code: str,
        terminal_no: int,
        report_scope: str,
        report_type: str,
        business_date: str,
        open_counter: int,
        business_counter: int,
        report_data: Any,
        requesting_terminal_no: int = None,
        requesting_staff_id: str = None,
    ) -> None:
        """
        Send generated report to journal service for archival.

        This method sends reports to the journal service so they can be stored
        and retrieved later. It determines the transaction type based on the
        report scope (flash/daily) and constructs the journal data accordingly.

        Args:
            store_code: Identifier for the store
            terminal_no: Terminal number (None for store-wide reports)
            report_scope: Scope of the report ('flash' or 'daily')
            report_type: Type of report (e.g., 'sales')
            business_date: Date for which the report was generated
            open_counter: Counter for terminal open/close cycles
            business_counter: Business counter for the day
            report_data: The generated report data
            requesting_terminal_no: Terminal that requested the report (for store-wide reports)
            requesting_staff_id: Staff ID who requested the report
        """
        logger.info(
            f"_send_report_to_journal called with: store_code={store_code}, terminal_no={terminal_no}, report_scope={report_scope}, requesting_terminal_no={requesting_terminal_no}"
        )
        try:
            # Determine transaction type based on report scope
            if report_scope == "flash":
                transaction_type = TransactionType.FlashReport.value
            elif report_scope == "daily":
                transaction_type = TransactionType.DailyReport.value
            else:
                logger.warning(f"Unknown report scope '{report_scope}', skipping journal")
                return

            # Extract receipt data if available
            receipt_text = ""
            journal_text = ""

            # The report_data is a SalesReportDocument instance (not wrapped in another object)
            if hasattr(report_data, "receipt_text") and report_data.receipt_text:
                receipt_text = report_data.receipt_text
            if hasattr(report_data, "journal_text") and report_data.journal_text:
                journal_text = report_data.journal_text
            else:
                # Convert report data to string representation if no journal_text
                import json

                journal_text = json.dumps(
                    report_data.model_dump() if hasattr(report_data, "model_dump") else report_data,
                    ensure_ascii=False,
                    indent=2,
                )

            # Set default receipt text if not available
            if not receipt_text:
                receipt_text = f"Report: {report_type} ({report_scope})\nStore: {store_code}\nDate: {business_date}"

            # Prepare journal data
            # The journal API schema uses camelCase due to alias_generator=to_lower_camel
            # Always use the requesting terminal number for journal
            # For terminal-specific reports: requesting_terminal_no should be the same as terminal_no
            # For store-wide reports: requesting_terminal_no is the terminal that requested the report
            journal_terminal_no = requesting_terminal_no or terminal_no or 0

            journal_data = {
                "tenantId": self.tenant_id,
                "storeCode": store_code,
                "terminalNo": journal_terminal_no,  # Always the requesting terminal
                "transactionType": transaction_type,
                "businessDate": business_date,
                "openCounter": open_counter or 0,
                "businessCounter": business_counter or 0,  # Fixed typo in journal API schema
                "generateDateTime": get_app_time_str(),
                "receiptNo": 0,  # Reports don't have receipt numbers
                "amount": 0.0,  # Will be set from report data if available
                "quantity": 0,  # Will be set from report data if available
                "staffId": requesting_staff_id or "SYSTEM",  # Default to SYSTEM for reports
                "userId": None,  # Set to None as requested
                "journalText": journal_text,
                "receiptText": receipt_text,
            }

            # For reports, amount and quantity are not applicable
            # Reports are summaries, not individual transactions
            # Keep them as 0 as originally intended

            # Send to journal service using the requesting terminal
            endpoint = f"/tenants/{self.tenant_id}/stores/{store_code}/terminals/{journal_terminal_no}/journals"

            # Generate service-to-service JWT token for authentication
            service_token = create_service_token(tenant_id=self.tenant_id, service_name="report")

            # Add Authorization header with Bearer token
            headers = {"Authorization": f"Bearer {service_token}"}

            async with get_service_client("journal") as client:
                response = await client.post(endpoint, json=journal_data, headers=headers)
                logger.info(
                    f"Report sent to journal successfully: {report_type} ({report_scope}) for {store_code}/{terminal_no or 'store'} (requested by terminal {journal_terminal_no})"
                )

        except HttpClientError as e:
            # Log the error but don't fail the report generation
            logger.error(f"Failed to send report to journal: {e.message}")
            if e.response:
                logger.error(f"Journal service response: {e.response}")
        except Exception as e:
            # Log any other errors but don't fail the report generation
            logger.error(f"Unexpected error sending report to journal: {str(e)}")

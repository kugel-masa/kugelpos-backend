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
from app.models.repositories.settlement_record_repository import SettlementRecordRepository
from app.exceptions.report_exceptions import SessionNotSettledException
from app.services.report_plugin_manager import ReportPluginManager
from app.exceptions import (
    ReportNotFoundException,
    ReportValidationException,
    ReportGenerationException,
    ReportTypeException,
    ReportScopeException,
    ReportDateException,
    ReportDataException,
)


def _refuse_half_date_range(business_date_from: str | None, business_date_to: str | None) -> None:
    """A date range is given by both ends or not at all.

    Most report makers read the range only when both ends are there and
    otherwise report the single business_date, so a half range was ignored
    rather than refused (#314). Checked here, ahead of every maker.
    """
    if bool(business_date_from) != bool(business_date_to):
        raise ReportDateException(
            "business_date_from and business_date_to must be provided together.", logger
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
        *,
        terminal_info_repository: TerminalInfoWebRepository = None,
        settlement_repository: SettlementRecordRepository = None,
    ):
        """
        Initialize the ReportService with required repositories.

        Args:
            tran_repository: Repository for transaction logs
            cash_in_out_log_repository: Repository for cash in/out operation logs
            open_close_log_repository: Repository for terminal open/close logs
            terminal_info_repository: Repository for terminal information
            settlement_repository: Settlement records, whose frozen daily reports
                the daily scope answers from (#343); built from the transaction
                repository's database when not given
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        self.settlement_repository = settlement_repository or SettlementRecordRepository(
            tran_repository.db, tran_repository.tenant_id
        )
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
            ReportDateException: If the date range is given by one end only
            SessionNotSettledException: If a session in scope is not settled (daily, #343)
            ReportGenerationException: If an error occurs during report generation
            ReportNotFoundException: If the requested report type does not exist
        """
        logger.debug(
            f"get_report_for_store_async: {store_code}, {report_scope}, {report_type}, {business_date}, {open_counter}, {limit}, {page}, {sort}"
        )
        _refuse_half_date_range(business_date_from, business_date_to)

        # Normalize report_scope: treat "flush" as "flash" for backward compatibility
        if report_scope == "flush":
            report_scope = "flash"

        if report_type in self.report_makers:
            try:
                maker = self.report_makers[report_type]
                
                # Check if the maker supports date range parameters
                if report_scope == "daily":
                    # From the settled sessions' frozen reports (#343)
                    report_data = await self._daily_report_async(
                        store_code=store_code,
                        report_type=report_type,
                        terminal_no=None,
                        business_date=business_date,
                        open_counter=open_counter,
                        business_counter=business_counter,
                        business_date_from=business_date_from,
                        business_date_to=business_date_to,
                    )
                elif hasattr(maker.generate_report, '__code__') and 'business_date_from' in maker.generate_report.__code__.co_varnames:
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
            except SessionNotSettledException:
                raise
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
            ReportDateException: If the date range is given by one end only
            SessionNotSettledException: If a session in scope is not settled (daily, #343)
            ReportGenerationException: If an error occurs during report generation
            ReportNotFoundException: If the requested report type does not exist
        """
        logger.debug(
            f"get_report_for_terminal_async: {store_code}, {terminal_no}, {report_scope}, {report_type}, {business_date}, {open_counter}, {limit}, {page}, {sort}"
        )
        _refuse_half_date_range(business_date_from, business_date_to)

        # Normalize report_scope: treat "flush" as "flash" for backward compatibility
        if report_scope == "flush":
            report_scope = "flash"

        if report_type in self.report_makers:
            try:
                maker = self.report_makers[report_type]
                
                # Check if the maker supports date range parameters
                if report_scope == "daily":
                    # From the settled sessions' frozen reports (#343)
                    report_data = await self._daily_report_async(
                        store_code=store_code,
                        report_type=report_type,
                        terminal_no=terminal_no,
                        business_date=business_date,
                        open_counter=open_counter,
                        business_counter=business_counter,
                        business_date_from=business_date_from,
                        business_date_to=business_date_to,
                    )
                elif hasattr(maker.generate_report, '__code__') and 'business_date_from' in maker.generate_report.__code__.co_varnames:
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
            except SessionNotSettledException:
                raise
            except Exception as e:
                if business_date_from and business_date_to:
                    message = f"Error occurred during report generation: report_type->{report_type}, store_code->{store_code}, terminal_no->{terminal_no}, date_range->{business_date_from} to {business_date_to}"
                else:
                    message = f"Error occurred during report generation: report_type->{report_type}, store_code->{store_code}, terminal_no->{terminal_no}, business_date->{business_date}"
                raise ReportGenerationException(message, logger, e) from e
        else:
            message = f"Invalid report type: {report_type}"
            raise ReportNotFoundException(message, logger)

    async def _sessions_in_scope_async(
        self,
        store_code: str,
        terminal_no: int = None,
        business_date: str = None,
        open_counter: int = None,
        business_counter: int = None,
        business_date_from: str = None,
        business_date_to: str = None,
    ) -> dict[tuple, dict]:
        """
        Every session with a log in a daily report's scope (#343, R-5).

        A session is (terminal_no, business_counter). Any open log, transaction
        log or cash log puts it in scope: such a session must be settled before
        a daily report can include it.

        Returns:
            (terminal_no, business_counter) -> {business_date, open_counter}
        """
        match: dict = {"tenant_id": self.tenant_id, "store_code": store_code}
        if business_date_from and business_date_to:
            match["business_date"] = {"$gte": business_date_from, "$lte": business_date_to}
        elif business_date:
            match["business_date"] = business_date
        if terminal_no is not None:
            match["terminal_no"] = terminal_no
        if open_counter is not None:
            match["open_counter"] = open_counter
        if business_counter is not None:
            match["business_counter"] = business_counter
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": {"terminal_no": "$terminal_no", "business_counter": "$business_counter"},
                    "business_date": {"$first": "$business_date"},
                    "open_counter": {"$first": "$open_counter"},
                }
            },
        ]
        sessions: dict[tuple, dict] = {}
        for repo in (self.open_close_log_repository, self.tran_repository, self.cash_in_out_log_repository):
            for row in await repo.execute_pipeline(pipeline):
                key = (row["_id"].get("terminal_no"), row["_id"].get("business_counter"))
                sessions.setdefault(key, {"business_date": row.get("business_date"), "open_counter": row.get("open_counter")})
        return sessions

    async def _daily_report_async(
        self,
        store_code: str,
        report_type: str,
        terminal_no: int = None,
        business_date: str = None,
        open_counter: int = None,
        business_counter: int = None,
        business_date_from: str = None,
        business_date_to: str = None,
    ) -> Any:
        """
        A daily report from the frozen reports of the settled sessions in scope (#343).

        Raises:
            SessionNotSettledException: A session in scope has no final settlement
        """
        scope = dict(
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            business_counter=business_counter,
            business_date_from=business_date_from,
            business_date_to=business_date_to,
        )
        sessions = await self._sessions_in_scope_async(store_code, **scope)
        records = await self.settlement_repository.find_final_async(store_code, **scope)
        settled = {(r.terminal_no, r.business_counter) for r in records}
        unsettled = [
            {"terminalNo": t, "businessCounter": bc, "businessDate": info["business_date"], "openCounter": info["open_counter"]}
            for (t, bc), info in sorted(sessions.items(), key=lambda kv: (kv[0][0] or 0, kv[0][1] or 0))
            # A log without a business_counter (from before every writer set it)
            # has no session to settle; it cannot hold a daily report hostage
            if (t, bc) not in settled and bc is not None
        ]
        if unsettled:
            raise SessionNotSettledException(
                f"Daily report refused: {len(unsettled)} session(s) not settled. store_code->{store_code}, scope->{scope}",
                unsettled,
                logger,
            )

        maker = self.report_makers[report_type]
        if not records:
            # Nothing in scope: the empty report, as before
            return await maker.generate_report(
                store_code=store_code,
                report_scope="daily",
                report_type=report_type,
                limit=100,
                page=1,
                sort=None,
                **scope,
            )

        records = sorted(records, key=lambda r: r.settled_at or "")
        frozen = await self.settlement_repository.get_daily_reports_async([r.settlement_id for r in records], report_type)
        absent = [r.settlement_id for r in records if r.settlement_id not in frozen]
        if absent:
            raise ServiceException(f"Frozen {report_type} reports missing for settlements {absent}", logger)
        reports = [frozen[r.settlement_id] for r in records]

        is_range = bool(business_date_from and business_date_to)
        if len(reports) == 1 and terminal_no is not None and not is_range:
            document = maker.from_saved(reports[0])
        else:
            document = maker.merge(
                reports,
                terminal_no=terminal_no,
                business_date=None if is_range else business_date,
                business_date_from=business_date_from,
                business_date_to=business_date_to,
                open_counter=open_counter,
                business_counter=business_counter,
                report_scope="daily",
                report_type=report_type,
            )
        document.missing_count = sum(r.missing_count for r in records)
        document.missing_ranges = [
            {
                "terminal_no": r.terminal_no,
                "business_date": r.business_date,
                "business_counter": r.business_counter,
                "first": m.first,
                "last": m.last,
            }
            for r in records
            for m in r.missing_ranges
        ]
        return document

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

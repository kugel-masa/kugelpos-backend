# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

# 不要なワイルドカードインポート削除（実際に使用される例外クラスがないため）
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.slack_notifier import send_fatal_error_notification
from kugel_common.enums import TransactionType

from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.services.journal_service import JournalService
from app.models.documents.jornal_document import JournalDocument

logger = getLogger(__name__)


class LogService:
    """
    Service class for handling various log operations.

    This class manages the creation of different types of logs (transaction logs,
    cash in/out logs, and terminal open/close logs) and ensures they are properly
    stored in the database along with corresponding journal entries.
    """

    def __init__(
        self,
        tran_repository: TranlogRepository,
        cash_in_out_log_repository: CashInOutLogRepository,
        open_close_log_repository: OpenCloseLogRepository,
        journal_service: JournalService,
    ) -> None:
        """
        Initialize the log service with required repositories and services.

        Args:
            tran_repository: Repository for transaction log operations
            cash_in_out_log_repository: Repository for cash in/out log operations
            open_close_log_repository: Repository for terminal open/close log operations
            journal_service: Service for journal entry operations
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository
        self.journal_service = journal_service

    async def receive_tranlog_async(self, tran: BaseTransaction) -> BaseTransaction:
        """
        Process and store a transaction log.

        This method creates a corresponding journal entry for the transaction
        and stores both the transaction log and journal entry in a single
        atomic transaction.

        Args:
            tran: The transaction log to process and store

        Returns:
            The stored transaction log

        Raises:
            Exception: If there is an error during the transaction process
        """

        # transaction type for cancellation transactions
        tran_type = tran.transaction_type
        if tran.transaction_type == TransactionType.NormalSales.value:
            if tran.sales.is_cancelled:
                tran_type = TransactionType.NormalSalesCancel.value

        journal_doc = JournalDocument(
            tenant_id=tran.tenant_id,
            store_code=tran.store_code,
            terminal_no=tran.terminal_no,
            transaction_no=tran.transaction_no,
            transaction_type=tran_type,  # Use the transaction type determined above
            business_date=tran.business_date,
            open_counter=tran.open_counter,
            business_counter=tran.business_counter,
            generate_date_time=tran.generate_date_time,
            receipt_no=tran.receipt_no,
            amount=tran.sales.total_amount_with_tax,
            quantity=tran.sales.total_quantity,
            staff_id=tran.staff.id,
            user_id=tran.user.id,
            journal_text=tran.journal_text,
            receipt_text=tran.receipt_text,
        )

        async with await self.tran_repository.start_transaction() as session:
            try:
                self.journal_service.journal_repository.set_session(session)
                return_tran = await self.tran_repository.create_tranlog_async(tran)
                await self.journal_service.receive_journal_async(journal_doc.model_dump())
                await self.tran_repository.commit_transaction()
                return return_tran
            except Exception as e:
                await self.tran_repository.abort_transaction()
                message = f"Failed to create transaction log & journal: {e}"
                logger.error(message)
                await send_fatal_error_notification(
                    message=message, error=e, service="journal", context=tran.model_dump()
                )
                raise e

    async def receive_cashlog_async(self, cashlog: CashInOutLog) -> CashInOutLog:
        """
        Process and store a cash in/out log.

        This method creates a corresponding journal entry for the cash operation
        and stores both the cash log and journal entry in a single atomic transaction.
        The transaction type is determined based on whether the amount is positive
        (cash in) or negative (cash out).

        Args:
            cashlog: The cash in/out log to process and store

        Returns:
            The stored cash in/out log

        Raises:
            Exception: If there is an error during the transaction process
        """
        if cashlog.amount > 0:
            tran_type = TransactionType.CashIn.value
        else:
            tran_type = TransactionType.CashOut.value

        journal_doc = JournalDocument(
            tenant_id=cashlog.tenant_id,
            store_code=cashlog.store_code,
            terminal_no=cashlog.terminal_no,
            transaction_type=tran_type,
            business_date=cashlog.business_date,
            open_counter=cashlog.open_counter,
            business_counter=cashlog.business_counter,
            generate_date_time=cashlog.generate_date_time,
            amount=cashlog.amount,
            staff_id=cashlog.staff_id,
            journal_text=cashlog.journal_text,
            receipt_text=cashlog.receipt_text,
        )

        async with await self.cash_in_out_log_repository.start_transaction() as session:
            try:
                self.journal_service.journal_repository.set_session(session)
                return_cashlog = await self.cash_in_out_log_repository.create_cash_in_out_log(cashlog)
                await self.journal_service.receive_journal_async(journal_doc.model_dump())
                await self.cash_in_out_log_repository.commit_transaction()
                return return_cashlog
            except Exception as e:
                await self.cash_in_out_log_repository.abort_transaction()
                message = f"Failed to create cash in/out log & journal: {e}"
                logger.error(message)
                await send_fatal_error_notification(
                    message=message, error=e, service="journal", context=cashlog.model_dump()
                )
                raise e

    async def receive_open_close_log_async(self, open_close_log: OpenCloseLog) -> OpenCloseLog:
        """
        Process and store a terminal open/close log.

        This method creates a corresponding journal entry for the terminal operation
        and stores both the open/close log and journal entry in a single atomic transaction.
        The transaction type is determined based on whether the operation is "open" or "close".

        Args:
            open_close_log: The open/close log to process and store

        Returns:
            The stored open/close log

        Raises:
            Exception: If there is an error during the transaction process
        """
        if open_close_log.operation == "open":
            tran_type = TransactionType.Open.value
        else:
            tran_type = TransactionType.Close.value

        journal_doc = JournalDocument(
            tenant_id=open_close_log.tenant_id,
            store_code=open_close_log.store_code,
            terminal_no=open_close_log.terminal_no,
            transaction_type=tran_type,
            business_date=open_close_log.business_date,
            open_counter=open_close_log.open_counter,
            business_counter=open_close_log.business_counter,
            generate_date_time=open_close_log.generate_date_time,
            staff_id=open_close_log.staff_id,
            journal_text=open_close_log.journal_text,
            receipt_text=open_close_log.receipt_text,
        )

        async with await self.open_close_log_repository.start_transaction() as session:
            try:
                self.journal_service.journal_repository.set_session(session)
                return_open_close_log = await self.open_close_log_repository.create_open_close_log(open_close_log)
                await self.journal_service.receive_journal_async(journal_doc.model_dump())
                await self.open_close_log_repository.commit_transaction()
                return return_open_close_log
            except Exception as e:
                await self.open_close_log_repository.abort_transaction()
                message = f"Failed to create open/close log & journal: {e}"
                logger.error(message)
                await send_fatal_error_notification(
                    message=message, error=e, service="journal", context=open_close_log.model_dump()
                )
                raise e

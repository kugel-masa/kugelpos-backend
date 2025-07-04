# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

# Import removed as the exception classes were not being used
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.slack_notifier import send_fatal_error_notification

from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.config.settings import settings

logger = getLogger(__name__)


class LogService:
    """
    Service for receiving and processing various operational logs.

    This service acts as a facade for different log repositories, providing
    a unified interface for storing transaction logs, cash operation logs,
    and terminal open/close logs in their respective data stores.
    """

    def __init__(
        self,
        tran_repository: TranlogRepository,
        cash_in_out_log_repository: CashInOutLogRepository,
        open_close_log_repository: OpenCloseLogRepository,
    ) -> None:
        """
        Initialize the LogService with repositories for different log types.

        Args:
            tran_repository: Repository for transaction logs
            cash_in_out_log_repository: Repository for cash in/out operation logs
            open_close_log_repository: Repository for terminal open/close logs
        """
        self.tran_repository = tran_repository
        self.cash_in_out_log_repository = cash_in_out_log_repository
        self.open_close_log_repository = open_close_log_repository

    async def receive_tranlog_async(self, tran: BaseTransaction) -> BaseTransaction:
        """
        Receive and store a transaction log.

        Args:
            tran: Transaction log document to store

        Returns:
            The stored transaction log document, possibly with additional fields populated
        """
        try:
            tran = await self.tran_repository.create_tranlog_async(tran)
            return tran
        except Exception as e:
            message = f"Failed to create transaction log: {e}"
            logger.error(message)
            # Notify about the error
            await send_fatal_error_notification(message=message, error=e, service="report", context=tran.model_dump())
            raise e

    async def receive_cashlog_async(self, cashlog: CashInOutLog) -> CashInOutLog:
        """
        Receive and store a cash in/out operation log.

        Args:
            cashlog: Cash in/out log document to store

        Returns:
            The stored cash in/out log document, possibly with additional fields populated
        """
        try:
            log = await self.cash_in_out_log_repository.create_cash_in_out_log(cashlog)
            return log
        except Exception as e:
            message = f"Failed to create cash in/out log: {e}"
            logger.error(message)
            # Notify about the error
            await send_fatal_error_notification(
                message=message, error=e, service="report", context=cashlog.model_dump()
            )
            raise e

    async def receive_open_close_log_async(self, open_close_log: OpenCloseLog) -> OpenCloseLog:
        """
        Receive and store a terminal open/close log.

        Args:
            open_close_log: Terminal open/close log document to store

        Returns:
            The stored open/close log document, possibly with additional fields populated
        """
        try:
            log = await self.open_close_log_repository.create_open_close_log(open_close_log)
            return log
        except Exception as e:
            message = f"Failed to create open/close log: {e}"
            logger.error(message)
            # Notify about the error
            await send_fatal_error_notification(
                message=message, error=e, service="report", context=open_close_log.model_dump()
            )
            raise e

# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from datetime import datetime, timedelta
import aiohttp
import json
import uuid

from kugel_common.utils.misc import get_app_time, get_app_time_str
from kugel_common.models.repositories.staff_master_web_repository import StaffMasterWebRepository
from kugel_common.models.repositories.store_info_web_repository import StoreInfoWebRepository
from kugel_common.utils.slack_notifier import send_warning_notification

from app.config.settings import settings
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.repositories.terminal_info_repository import TerminalInfoRepository
from app.models.repositories.cash_in_out_log_repository import CashInOutLogRepository
from app.models.repositories.open_close_log_repository import OpenCloseLogRepository
from app.models.repositories.tran_log_web_repository import TranlogWebRepository
from app.models.repositories.terminallog_delivery_status_repository import TerminallogDeliveryStatusRepository
from app.models.documents.cash_in_out_log import CashInOutLog
from app.models.documents.open_close_log import OpenCloseLog
from app.enums.function_mode import FunctionMode
from app.enums.terminal_status import TerminalStatus
from app.utils.pubsub_manager import PubsubManager
from app.exceptions import (
    # Basic exceptions
    NotFoundException,
    AlreadyExistException,
    # Terminal basic operation exceptions
    TerminalNotFoundException,
    TerminalAlreadyExistsException,
    # Terminal status exceptions
    TerminalStatusException,
    TerminalOpenException,
    TerminalCloseException,
    TerminalNotSignedInException,
    TerminalAlreadySignedInException,
    # Sign-in related exceptions
    SignInOutException,
    # Cash handling exceptions
    CashInOutException,
    # Store information exceptions
    StoreNotFoundException,
    # others
    ExternalServiceException,
    InternalErrorException,
    UnexpectedErrorException,
)


from app.services.receipt_data.cash_in_out_receipt_data import CashInOutReceiptData
from app.services.receipt_data.open_close_receipt_data import OpenCloseReceiptData

from logging import getLogger

logger = getLogger(__name__)


class TerminalService:
    """
    Terminal Service class that handles all terminal operations
    Including terminal management, cash operations, and terminal status changes
    """

    def __init__(
        self,
        terminal_info_repo: TerminalInfoRepository,
        staff_master_repo: StaffMasterWebRepository,
        store_info_repo: StoreInfoWebRepository,
        cash_in_out_log_repo: CashInOutLogRepository,
        open_close_log_repo: OpenCloseLogRepository,
        tran_log_repo: TranlogWebRepository,
        terminal_log_delivery_status_repo: TerminallogDeliveryStatusRepository,
        terminal_id: str = None,
    ) -> None:
        """
        Initialize a TerminalService instance with the required repositories

        Args:
            terminal_info_repo: Repository for terminal information
            staff_master_repo: Repository for staff information
            store_info_repo: Repository for store information
            cash_in_out_log_repo: Repository for cash in/out logs
            open_close_log_repo: Repository for open/close logs
            tran_log_repo: Repository for transaction logs
            terminal_id: Optional terminal ID to associate with this service instance
        """
        self.terminal_id = terminal_id
        self.terminal_info_repo = terminal_info_repo
        self.staff_master_repo = staff_master_repo
        self.store_info_repo = store_info_repo
        self.cash_in_out_log_repo = cash_in_out_log_repo
        self.open_close_log_repo = open_close_log_repo
        self.tran_log_repo = tran_log_repo
        self.terminal_log_delivery_status_repo = terminal_log_delivery_status_repo
        self.pubsub_manager = PubsubManager()

    # Terminal creation methods

    async def create_terminal_async(self, store_code: str, terminal_no: int, description: str) -> str:
        """
        Create a new terminal in the system

        Args:
            store_code: Store code to associate with the terminal
            terminal_no: Terminal number within the store
            description: Description of the terminal

        Returns:
            Terminal object that was created

        Raises:
            TerminalAlreadyExistsException: If the terminal already exists
        """

        try:
            terminal = await self.terminal_info_repo.create_terminal_info(store_code, terminal_no, description)
        except AlreadyExistException as e:
            message = f"Terminal already exists: {terminal_no}"
            raise TerminalAlreadyExistsException(message=message, logger=logger, original_exception=e)
        except Exception as e:
            raise e

        if terminal:
            self.terminal_id = terminal.terminal_id

        return terminal

    async def delete_terminal_async(self) -> bool:
        """
        Delete a terminal from the system

        Returns:
            bool: True if deletion was successful
        """
        result = await self.terminal_info_repo.delete_terminal_info_async(self.terminal_id)
        return result

    # Terminal update methods

    async def update_terminal_description_async(self, description: str) -> TerminalInfoDocument:
        """
        Update the description of a terminal

        Args:
            description: New description for the terminal

        Returns:
            Updated terminal information object

        Raises:
            TerminalNotFoundException: If the terminal is not found
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        update_dict = {"description": description}
        result = await self.terminal_info_repo.update_terminal_info_async(self.terminal_id, update_dict)
        return await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

    async def update_terminal_function_mode_async(self, function_mode: str) -> TerminalInfoDocument:
        """
        Update the function mode of a terminal
        Function mode determines what operations are allowed on the terminal

        Args:
            function_mode: New function mode for the terminal

        Returns:
            Updated terminal information object

        Raises:
            TerminalNotFoundException: If the terminal is not found
            TerminalStatusException: If the function mode change is not allowed in the current state
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        error_message = await self.__check_terminal_status(function_mode)
        logger.info(f"error_message: {error_message}")
        if not error_message is None:
            logger.info(f"check_terminal_status error_message: {error_message}")
            raise TerminalStatusException(message=error_message, logger=logger)

        update_dict = {"function_mode": function_mode}
        result = await self.terminal_info_repo.update_terminal_info_async(self.terminal_id, update_dict)
        return await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

    async def __check_terminal_status(self, function_mode: str) -> str:
        """
        Check if the requested function mode change is allowed in the current terminal state

        Args:
            function_mode: The function mode to switch to

        Returns:
            Error message if the change is not allowed, None if it's allowed
        """
        logger.info(f"function_mode: {function_mode}")

        only_enabled_in_opened = [
            FunctionMode.Sales.value,
            FunctionMode.Returns.value,
            FunctionMode.Void.value,
            FunctionMode.CloseTerminal.value,
            FunctionMode.CashInOut.value,
        ]

        only_enabled_not_in_opened = [FunctionMode.OpenTerminal.value]

        if await self.is_opened_async():
            logger.debug("terminal is opened")
            if function_mode in only_enabled_not_in_opened:
                logger.debug("only_enabled_not_in_opened")
            if function_mode in only_enabled_not_in_opened:
                return f"Terminal is already opened: {self.terminal_id}"
        else:
            logger.debug("terminal is not opened")
            if function_mode in only_enabled_in_opened:
                logger.debug("only_enabled_in_opened")
                return f"Terminal is not opened: {self.terminal_id}"

        return None

    # Terminal authentication methods

    async def sign_in_terminal_async(self, staff_id: str) -> TerminalInfoDocument:
        """
        Sign in a staff member to a terminal

        Args:
            staff_id: ID of the staff member to sign in

        Returns:
            Updated terminal information with staff details

        Raises:
            TerminalNotFoundException: If the terminal is not found
            TerminalAlreadySignedInException: If the terminal is already signed in
            SignInOutException: If the staff member is not found
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        # check if already signed in
        if terminal.staff is not None:
            message = f"Terminal is already signed in: {self.terminal_id}"
            raise TerminalAlreadySignedInException(message=message, logger=logger)

        try:
            staff = await self.staff_master_repo.get_staff_by_id_async(staff_id)
            terminal.staff = staff
        except NotFoundException as e:
            message = f"Staff not found: {staff_id}: {e} : logger -> {logger}"
            raise SignInOutException(message=message, logger=logger, original_exception=e)

        result = await self.terminal_info_repo.replace_terminal_info_async(self.terminal_id, terminal)
        return await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

    async def sign_out_terminal_async(self) -> TerminalInfoDocument:
        """
        Sign out the current staff member from a terminal

        Returns:
            Updated terminal information with staff details removed

        Raises:
            TerminalNotFoundException: If the terminal is not found
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)
        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        # check if already signed out
        if terminal.staff is None:
            logger.debug(f"Terminal is already signed out: {self.terminal_id}")
            return terminal

        # remove staff info
        terminal.staff = None

        result = await self.terminal_info_repo.replace_terminal_info_async(self.terminal_id, terminal)
        return await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

    # Cash handling methods

    async def cash_in_out_async(self, amount: float, description: str) -> CashInOutLog:
        """
        Process a cash in or out transaction on the terminal
        Positive amounts represent cash in, negative amounts represent cash out

        Args:
            amount: Amount of cash (positive for cash in, negative for cash out)
            description: Description of the transaction

        Returns:
            CashInOutLog: Log entry for the cash transaction

        Raises:
            TerminalNotFoundException: If the terminal is not found
            TerminalNotSignedInException: If the terminal is not signed in
            TerminalStatusException: If the terminal is not in the opened state
            CashInOutException: If the cash in/out operation fails
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        # check if terminal not signed in
        if terminal.staff is None:
            message = f"Terminal is not signed in: {self.terminal_id}"
            raise TerminalNotSignedInException(message=message, logger=logger)

        # check if terminal is not opened
        if terminal.status != TerminalStatus.Opened.value:
            message = f"Terminal is not opened: {self.terminal_id}"
            raise TerminalStatusException(message=message, logger=logger)

        # make cash_in_out_log
        cash_in_out_log = CashInOutLog()
        cash_in_out_log.tenant_id = terminal.tenant_id
        cash_in_out_log.store_code = terminal.store_code
        cash_in_out_log.store_name = await self._get_store_name()
        cash_in_out_log.terminal_no = terminal.terminal_no
        cash_in_out_log.staff_id = terminal.staff.id if terminal.staff is not None else None
        cash_in_out_log.staff_name = terminal.staff.name if terminal.staff is not None else None
        cash_in_out_log.business_date = terminal.business_date
        cash_in_out_log.open_counter = terminal.open_counter
        cash_in_out_log.business_counter = terminal.business_counter
        cash_in_out_log.amount = amount
        cash_in_out_log.description = description
        cash_in_out_log.generate_date_time = get_app_time_str()
        # add receipt_text and journal_text to cash_in_out_log
        receipt_maker = CashInOutReceiptData(name="CashInOutReceiptData", width=32)
        receipt_data = receipt_maker.make_receipt_data(cash_in_out_log)
        cash_in_out_log.receipt_text = receipt_data.receipt_text
        cash_in_out_log.journal_text = receipt_data.journal_text

        # set event_id for cash_in_out_log
        event_id = str(uuid.uuid4())
        message = self._convert_datetime(cash_in_out_log.model_dump())
        message["event_id"] = event_id
        message["event_type"] = "cash_in_out"
        event_distinations = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
        ]

        # save cash_in_out_log to database
        async with await self.cash_in_out_log_repo.start_transaction() as session:
            try:
                # set session for repositories
                self.terminal_log_delivery_status_repo.set_session(session)
                # create terminal_log_delivery_status
                await self.terminal_log_delivery_status_repo.create_status_async(
                    event_id=event_id, payload=message, services=event_distinations, terminal_info=terminal
                )
                # create cash_in_out_log
                cash_in_out_log = await self.cash_in_out_log_repo.create_cash_in_out_log(cash_in_out_log)
                await self.cash_in_out_log_repo.commit_transaction()
            except Exception as e:
                await self.cash_in_out_log_repo.abort_transaction()
                message = f"Cannot cash in/out. terminal_id: {self.terminal_id}, terminal: {terminal}"
                raise CashInOutException(message=message, logger=logger, original_exception=e)
            finally:
                # clear session
                self.terminal_log_delivery_status_repo.set_session(None)
                self.cash_in_out_log_repo.set_session(None)

        # publish cash_in_out_log to message queue
        await self._publish_cash_in_out_log_async(message)

        return cash_in_out_log

    # Terminal open/close methods

    async def open_terminal_async(self, initial_amout: float) -> OpenCloseLog:
        """
        Open a terminal for business operations

        Args:
            initial_amout: Initial cash amount in the drawer

        Returns:
            OpenCloseLog: Log entry for the terminal opening

        Raises:
            TerminalNotFoundException: If the terminal is not found
            TerminalStatusException: If the terminal is already opened
            TerminalOpenException: If the open operation fails
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        # check if terminal is already opened
        if terminal.status == TerminalStatus.Opened.value:
            message = f"Terminal is already opened: {self.terminal_id}"
            raise TerminalStatusException(message=message, logger=logger)

        if terminal.business_date == get_app_time().strftime("%Y%m%d"):
            terminal.open_counter += 1
        else:
            terminal.business_date = get_app_time().strftime("%Y%m%d")
            terminal.open_counter = 1

        terminal.business_counter += 1
        terminal.status = TerminalStatus.Opened.value
        terminal.initial_amount = initial_amout

        # make cash_in_out_log
        gen_datetime = get_app_time_str()
        cash_in_out_log = None
        if initial_amout is not None:
            cash_in_out_log = CashInOutLog()
            cash_in_out_log.tenant_id = terminal.tenant_id
            cash_in_out_log.store_code = terminal.store_code
            cash_in_out_log.store_name = await self._get_store_name()
            cash_in_out_log.terminal_no = terminal.terminal_no
            cash_in_out_log.staff_id = terminal.staff.id if terminal.staff is not None else None
            cash_in_out_log.staff_name = terminal.staff.name if terminal.staff is not None else None
            cash_in_out_log.business_date = terminal.business_date
            cash_in_out_log.open_counter = terminal.open_counter
            cash_in_out_log.business_counter = terminal.business_counter
            cash_in_out_log.amount = initial_amout
            cash_in_out_log.description = "Initial amount"
            cash_in_out_log.generate_date_time = gen_datetime
            # add receipt_text and journal_text to cash_in_out_log
            receipt_maker = CashInOutReceiptData(name="CashInOutReceiptData", width=32)
            receipt_data = receipt_maker.make_receipt_data(cash_in_out_log)
            cash_in_out_log.receipt_text = receipt_data.receipt_text
            cash_in_out_log.journal_text = receipt_data.journal_text

        # make open_close_log
        open_close_log = OpenCloseLog()
        open_close_log.tenant_id = terminal.tenant_id
        open_close_log.store_code = terminal.store_code
        open_close_log.store_name = await self._get_store_name()
        open_close_log.terminal_no = terminal.terminal_no
        open_close_log.staff_id = terminal.staff.id if terminal.staff is not None else None
        open_close_log.staff_name = terminal.staff.name if terminal.staff is not None else None
        open_close_log.business_date = terminal.business_date
        open_close_log.open_counter = terminal.open_counter
        open_close_log.business_counter = terminal.business_counter
        open_close_log.operation = "open"
        open_close_log.generate_date_time = gen_datetime
        open_close_log.terminal_info = terminal.model_copy()  # copy terminal info
        open_close_log.terminal_info.api_key = "****-****-****-****"  # hide api_key
        # add receipt_text and journal_text to open_close_log
        receipt_maker = OpenCloseReceiptData(name="OpenReceiptData", width=32)
        receipt_data = receipt_maker.make_receipt_data(open_close_log)
        open_close_log.receipt_text = receipt_data.receipt_text
        open_close_log.journal_text = receipt_data.journal_text

        # set event_id for open_close_log
        open_event_id = str(uuid.uuid4())
        open_message = self._convert_datetime(open_close_log.model_dump())
        open_message["event_id"] = open_event_id
        open_message["event_type"] = "open"
        open_event_distinations = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
        ]

        # set event_id for cash_in_out_log
        if cash_in_out_log is not None:
            cash_event_id = str(uuid.uuid4())
            cash_message = self._convert_datetime(cash_in_out_log.model_dump())
            cash_message["event_id"] = cash_event_id
            cash_event_distinations = [
                {"service_name": "report", "status": "pending"},
                {"service_name": "journal", "status": "pending"},
            ]

        # save cash_in_out_log to database and replace terminal info
        async with await self.open_close_log_repo.start_transaction() as session:
            try:
                # set session for repositories
                self.terminal_info_repo.set_session(session)
                self.cash_in_out_log_repo.set_session(session)
                self.terminal_log_delivery_status_repo.set_session(session)
                # update terminal info
                await self.terminal_info_repo.replace_terminal_info_async(self.terminal_id, terminal)
                # create cash_in_out_log
                if cash_in_out_log is not None:
                    await self.cash_in_out_log_repo.create_cash_in_out_log(cash_in_out_log)
                    await self.terminal_log_delivery_status_repo.create_status_async(
                        event_id=cash_event_id,
                        payload=cash_message,
                        services=cash_event_distinations,
                        terminal_info=terminal,
                    )
                # create open_close_log
                await self.open_close_log_repo.create_open_close_log(open_close_log)
                await self.terminal_log_delivery_status_repo.create_status_async(
                    event_id=open_event_id,
                    payload=open_message,
                    services=open_event_distinations,
                    terminal_info=terminal,
                )
                # commit transaction
                await self.open_close_log_repo.commit_transaction()
            except Exception as e:
                # abort transaction
                await self.open_close_log_repo.abort_transaction()
                message = f"Cannot open terminal. terminal_id: {self.terminal_id}, terminal: {terminal}"
                raise TerminalOpenException(message=message, logger=logger, original_exception=e)
            finally:
                # clear session
                self.terminal_info_repo.set_session(None)
                self.cash_in_out_log_repo.set_session(None)
                self.open_close_log_repo.set_session(None)
                self.terminal_log_delivery_status_repo.set_session(None)

        try:
            # publish cash_in_out_log and open_close_log to message queue
            if cash_in_out_log is not None:
                await self._publish_cash_in_out_log_async(cash_message)
            await self._publish_open_close_log(open_message)
        except Exception as e:
            raise e
        return open_close_log

    async def close_terminal_async(self, physical_amount: float) -> OpenCloseLog:
        """
        Close a terminal after business operations are complete

        Args:
            physical_amount: The physical cash amount counted in the drawer

        Returns:
            OpenCloseLog: Log entry for the terminal closing

        Raises:
            TerminalNotFoundException: If the terminal is not found
            TerminalStatusException: If the terminal is already closed or not opened
            TerminalCloseException: If the close operation fails
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)

        if terminal is None:
            message = f"Terminal not found: {self.terminal_id}"
            raise TerminalNotFoundException(message=message, logger=logger)

        # check if terminal is already closed
        if terminal.status == TerminalStatus.Closed.value:
            message = f"Terminal is already closed: {self.terminal_id}"
            raise TerminalStatusException(message=message, logger=logger)

        # check if terminal is not opened
        if terminal.status != TerminalStatus.Opened.value:
            message = f"Terminal is not opened: {self.terminal_id}"
            raise TerminalStatusException(message=message, logger=logger)

        terminal.status = TerminalStatus.Closed.value
        terminal.physical_amount = physical_amount

        # get cash_in_out_log list
        filter = {
            "tenant_id": terminal.tenant_id,
            "store_code": terminal.store_code,
            "terminal_no": terminal.terminal_no,
            "business_date": terminal.business_date,
            "open_counter": terminal.open_counter,
        }
        cash_in_out_log_list = await self.cash_in_out_log_repo.get_cash_in_out_logs(
            filter=filter,
            limit=1,
            page=1,
            sort=[("generate_date_time", -1)],
        )
        cash_in_out_log_count = cash_in_out_log_list.metadata.total
        cash_in_out_log_last_datetime = (
            cash_in_out_log_list.data[0].generate_date_time if cash_in_out_log_list.metadata.total > 0 else None
        )
        logger.debug(
            f"cash_in_out_log_count: {cash_in_out_log_count}, cash_in_out_log_last_datetime: {cash_in_out_log_last_datetime}"
        )

        # get tran_log list
        paginated_result = await self.tran_log_repo.get_tran_log_list_async(
            business_date=terminal.business_date,
            open_counter=terminal.open_counter,
            limit=1,
            page=1,
            sort=[("generate_date_time", -1)],
            include_cancelled=True,
        )
        logger.debug(f"paginated_result: {paginated_result}")
        tran_count = paginated_result.metadata.total
        if paginated_result.metadata.total > 0:
            tran_last_no = paginated_result.data[0].transaction_no
        else:
            tran_last_no = None
        logger.debug(f"tran_count: {tran_count}, tran_last_no: {tran_last_no}")

        # make open_close_log
        gen_datetime = get_app_time_str()
        open_close_log = OpenCloseLog()
        open_close_log.tenant_id = terminal.tenant_id
        open_close_log.store_code = terminal.store_code
        open_close_log.store_name = await self._get_store_name()
        open_close_log.terminal_no = terminal.terminal_no
        open_close_log.staff_id = terminal.staff.id if terminal.staff is not None else None
        open_close_log.staff_name = terminal.staff.name if terminal.staff is not None else None
        open_close_log.business_date = terminal.business_date
        open_close_log.open_counter = terminal.open_counter
        open_close_log.business_counter = terminal.business_counter
        open_close_log.operation = "close"
        open_close_log.generate_date_time = gen_datetime
        open_close_log.terminal_info = terminal
        open_close_log.cart_transaction_count = tran_count
        open_close_log.cart_transaction_last_no = tran_last_no
        open_close_log.cash_in_out_count = cash_in_out_log_count
        open_close_log.cash_in_out_last_datetime = cash_in_out_log_last_datetime
        receipt_maker = OpenCloseReceiptData(name="CloseReceiptData", width=32)
        receipt_data = receipt_maker.make_receipt_data(open_close_log)
        open_close_log.receipt_text = receipt_data.receipt_text
        open_close_log.journal_text = receipt_data.journal_text

        logger.debug(f"Terminal Close open_close_log: {open_close_log}")

        # set event_id for open_close_log
        close_event_id = str(uuid.uuid4())
        close_message = self._convert_datetime(open_close_log.model_dump())
        close_message["event_id"] = close_event_id
        close_message["event_type"] = "close"
        close_event_distinations = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
        ]

        # save open_close_log to database
        async with await self.open_close_log_repo.start_transaction() as session:
            try:
                # set session for repositories
                self.terminal_info_repo.set_session(session)
                self.terminal_log_delivery_status_repo.set_session(session)
                # update terminal info
                await self.terminal_info_repo.replace_terminal_info_async(self.terminal_id, terminal)
                # create open_close_log
                await self.open_close_log_repo.create_open_close_log(open_close_log)
                await self.terminal_log_delivery_status_repo.create_status_async(
                    event_id=close_event_id,
                    payload=close_message,
                    services=close_event_distinations,
                    terminal_info=terminal,
                )
                # commit transaction
                await self.open_close_log_repo.commit_transaction()
            except Exception as e:
                # abort transaction
                await self.open_close_log_repo.abort_transaction()
                message = f"Cannot close terminal. terminsl_id: {self.terminal_id}, terminal: {terminal}"
                raise TerminalCloseException(message=message, logger=logger, original_exception=e)
            finally:
                # clear session
                self.terminal_info_repo.set_session(None)
                self.open_close_log_repo.set_session(None)
                self.terminal_log_delivery_status_repo.set_session(None)

        try:
            # publish open_close_log to message queue
            await self._publish_open_close_log(close_message)
        except Exception as e:
            message = f"Cannot publish open_close_log. terminal_id: {self.terminal_id}, terminal: {terminal}"
            raise SystemError(message=message, logger=logger, original_exception=e)
        return open_close_log

    # Terminal information retrieval methods

    async def get_terminal_info_list_async(
        self, limit: int, page: int, sort: list[tuple[str, int]], store_code: str = None
    ) -> list[TerminalInfoDocument]:
        """
        Get a list of terminals with pagination

        Args:
            limit: Maximum number of results to return
            page: Page number to return
            sort: List of tuples containing field name and sort direction (1 for asc, -1 for desc)
            store_code: Optional filter by store code

        Returns:
            List of terminal information documents
        """
        return await self.terminal_info_repo.get_terminal_info_list_async(
            limit=limit, page=page, sort=sort, store_code=store_code
        )

    async def get_terminal_info_list_paginated_async(
        self, limit: int, page: int, sort: list[tuple[str, int]], store_code: str = None
    ):
        """
        Get a list of terminals with pagination metadata

        Args:
            limit: Maximum number of results to return
            page: Page number to return
            sort: List of tuples containing field name and sort direction (1 for asc, -1 for desc)
            store_code: Optional filter by store code

        Returns:
            PaginatedResult containing terminal information documents and metadata
        """
        return await self.terminal_info_repo.get_terminal_info_list_paginated_async(
            limit=limit, page=page, sort=sort, store_code=store_code
        )

    async def get_terminal_info_async(self) -> TerminalInfoDocument:
        """
        Get information for the current terminal
        Retrieves from cache if available, otherwise from repository

        Returns:
            Terminal information document
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)
        return terminal

    # Terminal status check methods

    async def is_sigin_in_async(self) -> bool:
        """
        Check if the terminal has a staff member signed in

        Returns:
            True if signed in, False otherwise
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)
        return terminal.staff is not None

    async def is_opened_async(self) -> bool:
        """
        Check if the terminal is in the opened state

        Returns:
            True if opened, False otherwise
        """
        terminal = await self.terminal_info_repo.get_terminal_info_by_id_async(self.terminal_id)
        logger.debug(f"terminal.status: {terminal.status}, TerminalStatus.Opened.value: {TerminalStatus.Opened.value}")
        return terminal.status == TerminalStatus.Opened.value

    # Message publishing methods
    async def _publish_cash_in_out_log_async(self, cashlog_dict: dict) -> None:
        """
        Publish cash in/out log to the message queue using Dapr pub/sub
        Non-blocking implementation that continues processing even if publishing fails

        Args:
            cash_in_out_log: Cash in/out log to publish
        """
        event_id = cashlog_dict["event_id"]
        pubsub_name = "pubsub-cashlog-report"
        topic_name = "topic-cashlog"

        # Use PubsubManager with circuit breaker pattern
        success, error_msg = await self.pubsub_manager.publish_message_async(
            pubsub_name=pubsub_name, topic_name=topic_name, message=cashlog_dict
        )

        if success:
            await self._update_delivery_status_internal_async(event_id, "published")
        else:
            # Update delivery status to failed if there's an error
            await self._update_delivery_status_internal_async(event_id=event_id, status="failed", message=error_msg)
            logger.error(f"Failed to publish cash in/out log: {error_msg}. Continuing processing...")

    async def _publish_open_close_log(self, open_close_dict: dict) -> None:
        """
        Publish open/close log to the message queue using Dapr pub/sub
        Non-blocking implementation that continues processing even if publishing fails

        Args:
            open_close_dict: Open/close log to publish
        """
        event_id = open_close_dict["event_id"]
        pubsub_name = "pubsub-opencloselog-report"
        topic_name = "topic-opencloselog"

        # Use PubsubManager with circuit breaker pattern
        success, error_msg = await self.pubsub_manager.publish_message_async(
            pubsub_name=pubsub_name, topic_name=topic_name, message=open_close_dict
        )

        if success:
            await self._update_delivery_status_internal_async(event_id, "published")
        else:
            # Update delivery status to failed if there's an error
            await self._update_delivery_status_internal_async(event_id=event_id, status="failed", message=error_msg)
            logger.error(f"Failed to publish open/close log: {error_msg}. Continuing processing...")

    async def _update_delivery_status_internal_async(
        self, event_id: str, status: str, service_name: str = None, message: str = None
    ) -> bool:
        """
        Update the delivery status of a transaction log.

        Args:
            event_id: The event ID of the transaction log
            status: The new delivery status (published/delivered/partially_delivered/failed)
            service_name: The name of the service to update (optional)
            message: Additional message to include with the status update (optional)
        Returns:
            bool: True if the update was successful, False otherwise
        """

        try:
            if service_name is not None:
                # update service status
                result = await self.terminal_log_delivery_status_repo.update_service_status(
                    event_id=event_id, service_name=service_name, status=status, message=message
                )
            else:
                # update overall delivery status
                result = await self.terminal_log_delivery_status_repo.update_delivery_status(
                    event_id=event_id, status=status
                )
            return result
        except Exception as e:
            message = f"Error updating delivery status: {e}"
            raise InternalErrorException(message, logger) from e

    async def update_delivery_status_async(self, event_id: str, status: str, service_name: str, message: str) -> None:
        """
        Update the delivery status of a transaction log.
        Args:
            event_id: The event ID of the transaction log
            status: The new delivery status (published/delivered/partially_delivered/failed)
            service_name: The name of the service to update
            message: Additional message to include with the status update
        Returns:
            None:
        """
        # Update the delivery status by notifying
        await self._update_delivery_status_internal_async(
            event_id=event_id, status=status, service_name=service_name, message=message
        )

        # check overall delivery status
        delivery_status = await self.terminal_log_delivery_status_repo.find_by_event_id(event_id=event_id)
        # check if all services are received
        if delivery_status is not None:

            # check if all services are received
            all_services_received = all(service.status == "received" for service in delivery_status.services)
            # check if any service is received
            any_service_received = any(service.status == "received" for service in delivery_status.services)
            # check if all services are failed
            all_services_failed = all(service.status == "failed" for service in delivery_status.services)

            if all_services_received:
                # update overall delivery status to delivered
                await self._update_delivery_status_internal_async(event_id=event_id, status="delivered")
            elif any_service_received:
                # update overall delivery status to partially_delivered
                await self._update_delivery_status_internal_async(event_id=event_id, status="partially_delivered")
            elif all_services_failed:
                # update overall delivery status to failed
                await self._update_delivery_status_internal_async(event_id=event_id, status="failed")
        else:
            message = f"Delivery status not found for event_id: {event_id}"
            raise InternalErrorException(message=message, logger=logger)

    # Utility methods

    def _convert_datetime(self, obj):
        """
        Convert datetime objects to ISO format strings in a nested structure

        Args:
            obj: Object that may contain datetime instances

        Returns:
            Object with datetime instances converted to strings
        """
        if isinstance(obj, dict):
            return {k: self._convert_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetime(i) for i in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    async def _get_store_name(self) -> str:
        """
        Get the name of the store associated with the current terminal

        Returns:
            Store name

        Raises:
            StoreNotFoundException: If the store information cannot be found
        """
        store_info = await self.store_info_repo.get_store_info_async()
        if store_info is None:
            message = f"Store info not found: {self.terminal_id}"
            raise StoreNotFoundException(message=message, logger=logger)

        if store_info is not None and store_info.store_name is not None:
            logger.debug(f"store_info: {store_info}")
            return store_info.store_name.strip()
        else:
            return None

    async def republish_undelivered_terminallog_async(self) -> None:
        """
        Republish undelivered terminal logs to the appropriate topics.

        This function retrieves undelivered terminal logs from the database
        and republishes them to the appropriate topics for processing.

        Returns:
            None
        """
        hours_ago = settings.UNDELIVERED_CHECK_PERIOD_IN_HOURS
        undelivered_terminallog_status_list = await self.terminal_log_delivery_status_repo.find_pending_deliveries(
            hours_ago=hours_ago
        )
        if not undelivered_terminallog_status_list:
            logger.debug("Don`t worry! No undelivered terminallogs found")
            return

        logger.warning(f"Undelivered terminallogs found: {len(undelivered_terminallog_status_list)}")

        for status in undelivered_terminallog_status_list:
            # Check if the terminal log is undelivered shorter than the threshold
            if status.created_at > datetime.now() - timedelta(minutes=settings.UNDELIVERED_CHECK_INTERVAL_IN_MINUTES):
                # Skip the terminal log if it was created recently
                logger.debug(f"Skipping terminallog: event_id->{status.event_id}")
                continue

            # Check if the terminal log is undelivered longer than the threshold
            failed_minutes = settings.UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES
            if status.created_at < datetime.now() - timedelta(minutes=failed_minutes):
                # Update the delivery status to "failed"
                await self._update_delivery_status_internal_async(event_id=status.event_id, status="failed")
                # notify warning
                await send_warning_notification(
                    message="Undelivered terminallog found: "
                    f"event_id->{status.event_id}, "
                    f"tenant_id->{status.tenant_id}, "
                    f"store_code->{status.store_code}, "
                    f"terminal_no->{status.terminal_no}",
                    service="terminal",
                    context=status.model_dump(),
                )
            # Determine log type based on payload content and republish
            logger.debug(f"Republishing terminallog: event_id->{status.event_id}, tenant_id->{status.tenant_id}")
            payload = status.payload
            log_type = None

            if payload["event_type"] == "cash_in_out":
                log_type = "cashlog"
                await self._publish_cash_in_out_log_async(payload)
            elif payload["event_type"] == "open" or payload["event_type"] == "close":
                log_type = "opencloselog"
                await self._publish_open_close_log(payload)
            else:
                logger.error(f"Unknown log type for message: event_id->{status.event_id}")
                # Update delivery status to failed for unknown log types
                await self._update_delivery_status_internal_async(
                    event_id=status.event_id, status="failed", message="Unknown log type"
                )
                continue

            logger.info(f"Republished {log_type}: event_id->{status.event_id}")

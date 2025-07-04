# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Any
from logging import getLogger
import aiohttp
import uuid
import json
import ast
from datetime import datetime, timedelta

logger = getLogger(__name__)

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.utils.misc import get_app_time_str, get_app_time
from kugel_common.enums import TransactionType
from kugel_common.utils.slack_notifier import send_warning_notification

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.tranlog_delivery_status_repository import (
    TranlogDeliveryStatusRepository,
)
from app.models.documents.tranlog_delivery_status_document import TranlogDeliveryStatus
from app.models.repositories.terminal_counter_repository import (
    TerminalCounterRepository,
)
from app.models.repositories.settings_master_web_repository import SettingsMasterWebRepository
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository
from app.models.repositories.transaction_status_repository import TransactionStatusRepository
from app.models.documents.cart_document import CartDocument
from app.models.receipt_types import validate_receipt_lines
from app.enums.counter_type import CounterType
from app.utils.settings import get_setting_value
from app.services.cart_strategy_manager import CartStrategyManager
from app.exceptions import (
    DocumentNotFoundException,
    BadRequestBodyException,
    StrategyPluginException,
    ExternalServiceException,
    InternalErrorException,
    AlreadyVoidedException,
    AlreadyRefundedException,
)
from app.config.settings import settings
from app.utils.pubsub_manager import PubsubManager


class TranService:
    """
    Transaction service for managing transaction logs.

    This service is responsible for creating, retrieving, and processing transaction logs.
    It handles the conversion of cart documents into transaction logs, manages transaction
    numbering, creates receipt data, and publishes transaction events.

    The class also provides functionality for handling void and return transactions,
    which reference original transactions.
    """

    def __init__(
        self,
        terminal_info: TerminalInfoDocument,
        terminal_counter_repo: TerminalCounterRepository,
        tranlog_repo: TranlogRepository,
        tranlog_delivery_status_repo: TranlogDeliveryStatusRepository,
        settings_master_repo: SettingsMasterWebRepository,
        payment_master_repo: PaymentMasterWebRepository,
        transaction_status_repo: TransactionStatusRepository,
    ):
        """
        Initialize the transaction service with required repositories and information.

        Args:
            terminal_info: Terminal information document
            terminal_counter_repo: Repository for managing terminal counters
            tranlog_repo: Repository for transaction logs
            settings_master_repo: Repository for settings
            payment_master_repo: Repository for payment methods
        """
        self.terminal_info = terminal_info
        self.terminal_counter_repository = terminal_counter_repo
        self.tranlog_repository = tranlog_repo
        self.tranlog_delivery_status_repo = tranlog_delivery_status_repo
        self.settings_master_repo = settings_master_repo
        self.payment_master_repo = payment_master_repo
        self.transaction_status_repo = transaction_status_repo

        # Initialize pubsub manager for publishing messages with circuit breaker
        self.pubsub_manager = PubsubManager()

        self.strategy_manager = CartStrategyManager()
        self.receipt_data_strategy: AbstractReceiptData = None

        try:
            # Load receipt_data plugins
            receipt_data_strategies = self.strategy_manager.load_strategies("receipt_data_strategies")
            logger.debug(f"receipt_data_strategies: {receipt_data_strategies}")

            # Select receipt_data plugin in receipt_data_strategies by name "default"
            self.receipt_data_strategy = next(
                (
                    receipt_data_strategy
                    for receipt_data_strategy in receipt_data_strategies
                    if receipt_data_strategy.name == "default"
                ),
                None,
            )
            logger.debug(f"receipt_data_strategy default: {self.receipt_data_strategy}")
        except Exception as e:
            message = f"Error loading receipt_data strategies: {e}"
            raise StrategyPluginException(message, logger) from e

    def convert_datetime(self, obj):
        """
        Convert datetime objects to ISO format strings in a dictionary or list.

        Recursively processes dictionaries and lists to convert all datetime objects
        to ISO format strings, which is necessary for JSON serialization.

        Args:
            obj: Object to process (dictionary, list, datetime, or other)

        Returns:
            The processed object with datetime objects converted to strings
        """
        if isinstance(obj, dict):
            return {k: self.convert_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_datetime(i) for i in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    async def create_tranlog_async(self, cart: CartDocument) -> BaseTransaction:
        """
        Create a transaction log from a cart document.

        Converts a cart document into a transaction log, assigns transaction and receipt
        numbers, calculates stamp duty if applicable, generates receipt data, saves
        the transaction log to the database, and publishes the transaction event.

        Args:
            cart: The cart document to convert to a transaction log

        Returns:
            BaseTransaction: The created transaction log

        Raises:
            InternalErrorException: If there's an error creating the transaction log
            ExternalServiceException: If there's an error publishing the transaction event
        """
        tranlog = BaseTransaction()
        tranlog.tenant_id = self.terminal_info.tenant_id
        tranlog.store_code = self.terminal_info.store_code
        tranlog.store_name = cart.store_name
        tranlog.terminal_no = self.terminal_info.terminal_no
        tranlog.transaction_no = await self.terminal_counter_repository.numbering_count(
            countType=CounterType.Transaction.value
        )
        tranlog.transaction_type = cart.transaction_type
        tranlog.business_date = cart.business_date
        tranlog.open_counter = self.terminal_info.open_counter
        tranlog.business_counter = self.terminal_info.business_counter
        tranlog.generate_date_time = get_app_time_str()
        tranlog.receipt_no = await self.terminal_counter_repository.numbering_count(
            countType=CounterType.Receipt.value,
            start_value=await self._get_setting_value_async("RECEIPT_NO_START_VALUE"),
            end_value=await self._get_setting_value_async("RECEIPT_NO_END_VALUE"),
        )
        tranlog.user = cart.user
        tranlog.sales = cart.sales
        tranlog.line_items = cart.line_items
        tranlog.payments = cart.payments
        tranlog.taxes = cart.taxes
        tranlog.subtotal_discounts = cart.subtotal_discounts

        # Set staff info
        staff = BaseTransaction.Staff()
        staff.id = self.terminal_info.staff.id
        staff.name = self.terminal_info.staff.name
        tranlog.staff = staff

        # Set stamp duty if applicable
        total_amount_with_tax = tranlog.sales.total_amount_with_tax
        tax_total_amount = sum([tax.tax_amount for tax in tranlog.taxes])
        total_amount_without_tax = total_amount_with_tax - tax_total_amount
        cash_amount = sum([payment.amount for payment in tranlog.payments if payment.payment_code == "01"])

        for stamp_duty in settings.STAMP_DUTY_MASTER:
            target_amount = stamp_duty["target_amount"]
            if target_amount <= total_amount_without_tax and target_amount <= cash_amount:
                tranlog.sales.is_stamp_duty_applied = True
                tranlog.sales.stamp_duty_target_amount = cash_amount
                tranlog.sales.stamp_duty_amount = float(stamp_duty["stamp_duty_amount"])
                break
        # set invoice registration number
        tranlog.additional_info = {}
        invoice_registration_number = await self._get_setting_value_async("INVOICE_REGISTRATION_NUMBER")
        if invoice_registration_number is not None:
            try:
                if isinstance(invoice_registration_number, str):
                    tranlog.additional_info["invoice_registration_number"] = invoice_registration_number
                    logger.debug(f"Invoice registration number set: {invoice_registration_number}")
                else:
                    message = f"Invalid INVOICE_REGISTRATION_NUMBER format: {invoice_registration_number}"
                    logger.warning(message)
            except Exception as e:
                logger.warning(f"Error processing invoice registration number: {e}")

        # Set receipt header
        # Expected format: [{"text": "Header 1", "align": "left"}, {"text": "Header 2", "align": "right"}]
        # Note: Settings stored as strings in MongoDB may use single quotes (Python str() representation)
        receipt_headers = await self._get_setting_value_async("RECEIPT_HEADERS")
        if receipt_headers is not None:
            try:
                # Parse the setting value which may be stored as a string
                parsed_headers = await self._parse_json_or_literal_async(receipt_headers, "RECEIPT_HEADERS")

                if parsed_headers is not None:
                    validated_headers = validate_receipt_lines(parsed_headers)
                    if validated_headers:
                        tranlog.additional_info["receipt_headers"] = [
                            {"text": header["text"], "align": header["align"]} for header in validated_headers
                        ]
                        logger.debug(f"Receipt headers set: {len(validated_headers)} lines")
                    else:
                        logger.warning("No valid receipt headers found in RECEIPT_HEADERS")
            except Exception as e:
                logger.warning(f"Error processing receipt headers: {e}")

        # Set receipt footer
        # Expected format: [{"text": "Footer 1", "align": "left"}, {"text": "Footer 2", "align": "right"}]
        # Note: Settings stored as strings in MongoDB may use single quotes (Python str() representation)
        receipt_footers = await self._get_setting_value_async("RECEIPT_FOOTERS")
        if receipt_footers is not None:
            try:
                # Parse the setting value which may be stored as a string
                parsed_footers = await self._parse_json_or_literal_async(receipt_footers, "RECEIPT_FOOTERS")

                if parsed_footers is not None:
                    validated_footers = validate_receipt_lines(parsed_footers)
                    if validated_footers:
                        tranlog.additional_info["receipt_footers"] = [
                            {"text": footer["text"], "align": footer["align"]} for footer in validated_footers
                        ]
                        logger.debug(f"Receipt footers set: {len(validated_footers)} lines")
                    else:
                        logger.warning("No valid receipt footers found in RECEIPT_FOOTERS")
            except Exception as e:
                logger.warning(f"Error processing receipt footers: {e}")

        # Make receipt data
        try:
            print_data = self.receipt_data_strategy.make_receipt_data(tranlog)
        except Exception as e:
            message = f"Error making receipt data: {e}"
            raise InternalErrorException(message, logger) from e
        tranlog.receipt_text = print_data.receipt_text
        tranlog.journal_text = print_data.journal_text

        logger.debug(f"TranService.create_tranlog: tranlog->{tranlog}")

        # set event_id for tranlog
        event_id = str(uuid.uuid4())
        event_message = self.convert_datetime(tranlog.model_dump())
        event_message["event_id"] = event_id  # add event_id to tranlog dict
        event_distinations = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
            {"service_name": "stock", "status": "pending"},
        ]

        # Save tranlog to database
        async with await self.tranlog_repository.start_transaction() as session:
            try:
                self.tranlog_delivery_status_repo.set_session(session)
                await self.tranlog_delivery_status_repo.create_status_async(
                    event_id=event_id,
                    transaction_no=tranlog.transaction_no,
                    payload=event_message,
                    services=event_distinations,
                )
                tranlog = await self.tranlog_repository.create_tranlog_async(tranlog)
                await self.tranlog_repository.commit_transaction()

            except Exception as e:
                await self.tranlog_repository.abort_transaction()
                message = f"Error creating tranlog: {e}"
                raise InternalErrorException(message, logger) from e
            finally:
                # clear session
                self.tranlog_repository.set_session(session=None)
                self.tranlog_delivery_status_repo.set_session(session=None)

        # Publish tranlog
        await self._publish_tranlog_async(event_message)

        # Update cart_doc data
        cart.transaction_no = tranlog.transaction_no
        cart.receipt_no = tranlog.receipt_no
        cart.staff = tranlog.staff
        cart.receipt_text = tranlog.receipt_text
        cart.journal_text = tranlog.journal_text

        return tranlog

    async def get_tranlog_by_query_async(
        self,
        store_code: str,
        terminal_no: int,
        business_date: str = None,
        open_counter: int = None,
        transaction_type: list[int] = None,
        receipt_no: int = None,
        limit: int = 100,
        page: int = 1,
        sort: list[tuple[str, int]] = None,
        include_cancelled: bool = False,
    ):
        """
        Retrieve transaction logs matching specified criteria.

        Queries the transaction repository for transaction logs that match
        the provided filters, with pagination support.

        Args:
            store_code: Store code filter
            terminal_no: Terminal number filter
            business_date: Optional business date filter
            open_counter: Optional open counter number filter
            transaction_type: Optional list of transaction types to include
            receipt_no: Optional receipt number filter
            limit: Maximum number of records to return per page
            page: Page number to retrieve
            sort: List of field name and direction tuples for sorting
            include_cancelled: Whether to include cancelled transactions

        Returns:
            PaginatedResult: Paginated list of matching transaction logs with void/return status
        """
        # Get transactions from repository
        paginated_result = await self.tranlog_repository.get_tranlog_list_by_query_async(
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            transaction_type=transaction_type,
            receipt_no=receipt_no,
            limit=limit,
            page=page,
            sort=sort,
            include_cancelled=include_cancelled,
        )

        # Merge void/return status from history
        if paginated_result.data:
            paginated_result.data = await self.get_transaction_list_with_status_async(paginated_result.data)

        return paginated_result

    async def get_tranlog_by_transaction_no_async(self, store_code: str, terminal_no: int, transaction_no: int):
        """
        Retrieve a specific transaction log by its transaction number.

        Args:
            store_code: Store code where the transaction occurred
            terminal_no: Terminal number where the transaction occurred
            transaction_no: Unique transaction number to retrieve

        Returns:
            BaseTransaction: The retrieved transaction log

        Raises:
            DocumentNotFoundException: If the transaction is not found
        """
        tran = await self.tranlog_repository.get_tranlog_by_transaction_no_async(
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
        )
        if tran is None:
            message = f"Transaction not found: transaction_no->{transaction_no}"
            raise DocumentNotFoundException(message, logger)

        # Merge void/return status from history for single transaction
        transaction_list = await self.get_transaction_list_with_status_async([tran])
        return transaction_list[0] if transaction_list else tran

    async def void_async(self, tran: BaseTransaction, add_payment_list: list[dict[str, any]]) -> BaseTransaction:
        """
        Process a void transaction for an existing transaction.

        Creates a new void transaction that references the original transaction.
        The payment methods and amounts must match the original transaction.

        Args:
            tran: The original transaction to void
            add_payment_list: List of payments for the void transaction

        Returns:
            BaseTransaction: The created void transaction

        Raises:
            BadRequestBodyException: If payment information is invalid
            DocumentNotFoundException: If a payment method is not found
            InternalErrorException: If there's an error processing the void transaction
            ExternalServiceException: If there's an error publishing the transaction event
            AlreadyVoidedException: If the transaction has already been voided
        """
        # Check if the transaction has already been voided from history
        status = await self.transaction_status_repo.get_status_by_transaction_async(
            tran.tenant_id, tran.store_code, tran.terminal_no, tran.transaction_no
        )

        if status and status.is_voided:
            message = f"Transaction has already been voided: transaction_no->{tran.transaction_no}"
            raise AlreadyVoidedException(message, logger)

        # Only prevent voiding normal sales that have been refunded
        # Return transactions can be voided (to create VoidReturn transactions)
        if status and status.is_refunded and tran.transaction_type == TransactionType.NormalSales.value:
            message = f"Transaction has already been refunded: transaction_no->{tran.transaction_no}"
            raise AlreadyRefundedException(message, logger)

        # Set original transaction fields
        if tran.origin is None:
            tran.origin = BaseTransaction.OriginalTransaction()
        tran.origin.tenant_id = tran.tenant_id
        tran.origin.store_code = tran.store_code
        tran.origin.store_name = tran.store_name
        tran.origin.terminal_no = tran.terminal_no
        tran.origin.transaction_no = tran.transaction_no
        tran.origin.transaction_type = tran.transaction_type
        tran.origin.receipt_no = tran.receipt_no
        tran.origin.generate_date_time = tran.generate_date_time

        # Check if payment list is provided
        if add_payment_list is None:
            message = "Payment list is required for return transaction"
            raise BadRequestBodyException(message, logger)

        # Check if payment list is included in the original transaction
        for payment in add_payment_list:
            payment_code = payment.get("payment_code")
            if payment_code not in [p.payment_code for p in tran.payments]:
                message = f"Payment not found in original transaction: payment_code->{payment_code}"
                raise BadRequestBodyException(message, logger)
            payment_amount = payment.get("amount")
            payment_amount_original = sum([p.amount for p in tran.payments if p.payment_code == payment_code])
            if payment_amount != payment_amount_original:
                message = f"Payment amount must be equal for void transaction: payment_code->{payment_code}, payment_amount->{payment_amount}, payment_amount_original->{payment_amount_original}"
                raise BadRequestBodyException(message, logger)

        tran.payments = []
        for payment in add_payment_list:
            payment_code = payment.get("payment_code")
            pay_doc = await self.payment_master_repo.get_payment_by_code_async(payment_code)
            if pay_doc is None:
                message = f"PaymentMaster not found: payment_code->{payment_code}"
                raise DocumentNotFoundException(message, logger)

            tran_payment = BaseTransaction.Payment()
            tran_payment.payment_no = len(tran.payments) + 1
            tran_payment.payment_code = pay_doc.payment_code
            tran_payment.description = pay_doc.description
            if pay_doc.can_deposit_over and pay_doc.can_change:
                tran_payment.deposit_amount = payment.get("amount")
            tran_payment.amount = payment.get("amount")
            tran_payment.detail = payment.get("detail")
            tran.payments.append(tran_payment)

        # Check if payment amount is valid
        total_payment_amount = sum([payment.amount for payment in tran.payments])
        if total_payment_amount != tran.sales.total_amount_with_tax:
            message = f"Invalid payment amount for return transaction: total_payment_amount->{total_payment_amount}"
            raise BadRequestBodyException(message, logger)

        # Set fields for void transaction
        if tran.transaction_type == TransactionType.NormalSales.value:
            tran.transaction_type = TransactionType.VoidSales.value
        elif tran.transaction_type == TransactionType.ReturnSales.value:
            tran.transaction_type = TransactionType.VoidReturn.value
        else:
            message = f"Invalid transaction type to void: transaction_type->{tran.transaction_type}"
            raise BadRequestBodyException(message, logger)

        tran.transaction_no = await self.terminal_counter_repository.numbering_count(CounterType.Transaction.value)
        tran.receipt_no = await self.terminal_counter_repository.numbering_count(CounterType.Receipt.value)
        tran.generate_date_time = get_app_time_str()
        tran.sales.reference_date_time = tran.generate_date_time
        tran.sales.change_amount = 0  # change amount is not applicable for void transaction
        tran.business_date = self.terminal_info.business_date
        tran.business_counter = self.terminal_info.business_counter
        tran.open_counter = self.terminal_info.open_counter

        # Note: We don't set tran.is_voided here per requirement
        # The flag will be tracked in the transaction_status collection

        # Make receipt data
        try:
            print_data = self.receipt_data_strategy.make_receipt_data(tran)
        except Exception as e:
            message = f"Error making receipt data: {e}"
            raise InternalErrorException(message, logger) from e
        tran.receipt_text = print_data.receipt_text
        tran.journal_text = print_data.journal_text

        # set event_id for tranlog
        event_id = str(uuid.uuid4())
        event_message = self.convert_datetime(tran.model_dump())
        event_message["event_id"] = event_id  # add event_id to tranlog dict
        event_distinations = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
            {"service_name": "stock", "status": "pending"},
        ]

        # Save tranlog to database
        async with await self.tranlog_repository.start_transaction() as session:
            try:
                self.tranlog_delivery_status_repo.set_session(session)
                await self.tranlog_delivery_status_repo.create_status_async(
                    event_id=event_id,
                    transaction_no=tran.transaction_no,
                    payload=event_message,
                    services=event_distinations,
                )
                tran = await self.tranlog_repository.create_tranlog_async(tran)
                await self.tranlog_repository.commit_transaction()
            except Exception as e:
                await self.tranlog_repository.abort_transaction()
                message = f"Error creating tranlog: {e}"
                raise InternalErrorException(message, logger) from e
            finally:
                # clear session
                self.tranlog_repository.set_session(session=None)
                self.tranlog_delivery_status_repo.set_session(session=None)

        # Publish tranlog
        await self._publish_tranlog_async(event_message)

        # Mark the original transaction as voided in history
        await self.transaction_status_repo.mark_as_voided_async(
            tenant_id=tran.origin.tenant_id,
            store_code=tran.origin.store_code,
            terminal_no=tran.origin.terminal_no,
            transaction_no=tran.origin.transaction_no,
            void_transaction_no=tran.transaction_no,
            staff_id=tran.staff.id,
        )

        # If we're voiding a return transaction, reset the refund status on the original sale
        if tran.transaction_type == TransactionType.VoidReturn.value:
            # The origin contains the return transaction info
            # We need to find the original sale transaction that was refunded
            return_tran = await self.tranlog_repository.get_one_async({
                "tenant_id": tran.origin.tenant_id,
                "store_code": tran.origin.store_code,
                "terminal_no": tran.origin.terminal_no,
                "transaction_no": tran.origin.transaction_no,
            })

            if return_tran and return_tran.origin:
                # Reset the refund status on the original sale transaction
                await self.transaction_status_repo.reset_refund_status_async(
                    tenant_id=return_tran.origin.tenant_id,
                    store_code=return_tran.origin.store_code,
                    terminal_no=return_tran.origin.terminal_no,
                    transaction_no=return_tran.origin.transaction_no,
                )

        return tran

    async def return_async(self, tran: BaseTransaction, add_payment_list: list[dict[str, any]]) -> BaseTransaction:
        """
        Process a return transaction for an existing transaction.

        Creates a new return transaction that references the original transaction.
        The payment methods and amounts must be specified for the return.

        Args:
            tran: The original transaction to create a return for
            add_payment_list: List of payments for the return transaction

        Returns:
            BaseTransaction: The created return transaction

        Raises:
            BadRequestBodyException: If payment information is invalid or transaction type is unsupported
            DocumentNotFoundException: If a payment method is not found
            InternalErrorException: If there's an error processing the return transaction
            ExternalServiceException: If there's an error publishing the transaction event
            AlreadyRefundedException: If the transaction has already been refunded
        """
        # Check if the transaction has already been refunded or voided from history
        status = await self.transaction_status_repo.get_status_by_transaction_async(
            tran.tenant_id, tran.store_code, tran.terminal_no, tran.transaction_no
        )

        if status and status.is_refunded:
            message = f"Transaction has already been refunded: transaction_no->{tran.transaction_no}"
            raise AlreadyRefundedException(message, logger)

        if status and status.is_voided:
            message = f"Transaction has already been voided: transaction_no->{tran.transaction_no}"
            raise AlreadyVoidedException(message, logger)

        # Set original transaction fields
        if tran.origin is None:
            tran.origin = BaseTransaction.OriginalTransaction()
        tran.origin.tenant_id = tran.tenant_id
        tran.origin.store_code = tran.store_code
        tran.origin.store_name = tran.store_name
        tran.origin.terminal_no = tran.terminal_no
        tran.origin.transaction_no = tran.transaction_no
        tran.origin.transaction_type = tran.transaction_type
        tran.origin.receipt_no = tran.receipt_no
        tran.origin.generate_date_time = tran.generate_date_time

        # Check if transaction type is valid for return
        if tran.transaction_type != TransactionType.NormalSales.value:
            message = f"Invalid transaction type to return: transaction_type->{tran.transaction_type}"
            raise BadRequestBodyException(message, logger)

        # Check if payment list is provided
        if add_payment_list is None:
            message = "Payment list is required for return transaction"
            raise BadRequestBodyException(message, logger)

        tran.payments = []
        for payment in add_payment_list:
            payment_code = payment.get("payment_code")
            pay_doc = await self.payment_master_repo.get_payment_by_code_async(payment_code)
            if pay_doc is None:
                message = f"PaymentMaster not found: payment_code->{payment_code}"
                raise DocumentNotFoundException(message, logger)

            tran_payment = BaseTransaction.Payment()
            tran_payment.payment_no = len(tran.payments) + 1
            tran_payment.payment_code = pay_doc.payment_code
            tran_payment.description = pay_doc.description
            if pay_doc.can_deposit_over and pay_doc.can_change:
                tran_payment.deposit_amount = payment.get("amount")
            tran_payment.amount = payment.get("amount")
            tran_payment.detail = payment.get("detail")
            tran.payments.append(tran_payment)

        # Check if payment amount is valid
        total_payment_amount = sum([payment.amount for payment in tran.payments])
        if total_payment_amount != tran.sales.total_amount_with_tax:
            message = f"Invalid payment amount for return transaction: total_payment_amount->{total_payment_amount}"
            raise BadRequestBodyException(message, logger)

        # Set fields for return transaction
        tran.transaction_type = TransactionType.ReturnSales.value
        tran.transaction_no = await self.terminal_counter_repository.numbering_count(CounterType.Transaction.value)
        tran.receipt_no = await self.terminal_counter_repository.numbering_count(CounterType.Receipt.value)
        tran.generate_date_time = get_app_time_str()
        tran.sales.reference_date_time = tran.generate_date_time
        tran.sales.change_amount = 0  # change amount is not applicable for return transaction
        tran.business_date = self.terminal_info.business_date
        tran.business_counter = self.terminal_info.business_counter
        tran.open_counter = self.terminal_info.open_counter

        # Note: We don't set tran.is_refunded here per requirement
        # The flag will be tracked in the transaction_status collection

        # Make receipt data
        print_data = self.receipt_data_strategy.make_receipt_data(tran)
        tran.receipt_text = print_data.receipt_text
        tran.journal_text = print_data.journal_text

        # set event_id for tranlog
        event_id = str(uuid.uuid4())
        event_message = self.convert_datetime(tran.model_dump())
        event_message["event_id"] = event_id  # add event_id to tranlog dict
        event_distinations = [
            {"service_name": "report", "status": "pending"},
            {"service_name": "journal", "status": "pending"},
            {"service_name": "stock", "status": "pending"},
        ]

        # Save tranlog to database
        async with await self.tranlog_repository.start_transaction() as session:
            try:
                self.tranlog_delivery_status_repo.set_session(session)
                await self.tranlog_delivery_status_repo.create_status_async(
                    event_id=event_id,
                    transaction_no=tran.transaction_no,
                    payload=event_message,
                    services=event_distinations,
                )
                tran = await self.tranlog_repository.create_tranlog_async(tran)
                await self.tranlog_repository.commit_transaction()
            except Exception as e:
                await self.tranlog_repository.abort_transaction()
                message = f"Error creating tranlog: {e}"
                raise InternalErrorException(message, logger) from e
            finally:
                # clear session
                self.tranlog_repository.set_session(session=None)
                self.tranlog_delivery_status_repo.set_session(session=None)

        # Publish tranlog
        await self._publish_tranlog_async(event_message)

        # Mark the original transaction as refunded in history
        await self.transaction_status_repo.mark_as_refunded_async(
            tenant_id=tran.origin.tenant_id,
            store_code=tran.origin.store_code,
            terminal_no=tran.origin.terminal_no,
            transaction_no=tran.origin.transaction_no,
            return_transaction_no=tran.transaction_no,
            staff_id=tran.staff.id,
        )

        return tran

    async def _get_setting_value_async(self, name: str) -> Any:
        """
        Get a setting value from the settings repository.

        Retrieves a setting value by name, with appropriate terminal and store context.

        Args:
            name: Name of the setting to retrieve

        Returns:
            Any: The setting value
        """
        logger.debug(f"TranService._get_setting_value: name->{name}")

        try:
            setting_doc = await self.settings_master_repo.get_settings_value_by_name_async(name)
        except Exception:
            setting_doc = None
        finally:
            logger.debug(f"TranService._get_setting_value: setting_doc->{setting_doc}")

        return get_setting_value(
            name=name,
            store_code=self.terminal_info.store_code,
            terminal_no=self.terminal_info.terminal_no,
            setting=setting_doc,
        )

    async def _parse_json_or_literal_async(self, value: Any, setting_name: str) -> Any:
        """
        Parse a setting value that may be stored as a JSON string or Python literal.

        This method handles the common case where list/dict settings are stored as strings
        in MongoDB. It attempts multiple parsing strategies:
        1. If already a list/dict, return as-is
        2. Try standard JSON parsing (double quotes)
        3. Try Python literal evaluation (single quotes)
        4. Try quote replacement as last resort

        Args:
            value: The value to parse (may be string, list, dict, etc.)
            setting_name: Name of the setting for logging purposes

        Returns:
            Parsed value or None if parsing fails
        """
        # If already parsed, return as-is
        if isinstance(value, (list, dict)):
            return value

        # If not a string, return None
        if not isinstance(value, str):
            logger.warning(f"Unexpected type for {setting_name}: {type(value)}")
            return None

        # Try multiple parsing strategies
        # 1. Standard JSON (double quotes)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

        # 2. Python literal (single quotes, safe eval)
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass

        # 3. Quote replacement (risky but sometimes necessary)
        try:
            value_with_double_quotes = value.replace("'", '"')
            return json.loads(value_with_double_quotes)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse {setting_name}: {e}")
            return None

    async def _publish_tranlog_async(self, tranlog_dict: dict) -> None:
        """
        Publish a transaction log to the tranlog topic using Dapr.
        Non-blocking implementation that continues processing even if publishing fails.

        Converts the transaction log to a dictionary with proper datetime handling
        and publishes it to the tranlog topic for other services to consume.

        Args:
            tranlog_dict: The transaction log dictionary to publish
        """
        logger.debug(f"tranlog dict: {tranlog_dict}")
        event_id = tranlog_dict["event_id"]

        pubsub_name = "pubsub-tranlog-report"
        topic_name = "topic-tranlog"

        # Use PubsubManager with circuit breaker pattern
        success, error_msg = await self.pubsub_manager.publish_message_async(
            pubsub_name=pubsub_name, topic_name=topic_name, message=tranlog_dict
        )

        if success:
            await self._update_delivery_status_internal_async(event_id=event_id, status="published")
        else:
            # Update delivery status to failed if there's an error
            await self._update_delivery_status_internal_async(event_id=event_id, status="failed", message=error_msg)
            logger.error(f"Failed to publish transaction log: {error_msg}. Continuing processing...")

    async def _update_delivery_status_internal_async(
        self, event_id: str, status: str, service_name: str = None, message: str = None
    ) -> bool:
        """
        Update the delivery status of a transaction log.

        Args:
            event_id: The event ID of the transaction log
            status: The new delivery status (published/delivered/partially_delivered/failed)
            service_name: Optional name of the service to update status for. If None, updates the overall status

        Returns:
            bool: True if the update was successful, False otherwise
        """
        logger.debug(
            f"Updating delivery status: event_id->{event_id}, status->{status}, service_name->{service_name}, message->{message}"
        )
        try:
            if service_name:
                result = await self.tranlog_delivery_status_repo.update_service_status(
                    event_id=event_id, service_name=service_name, status=status, message=message
                )
            else:
                result = await self.tranlog_delivery_status_repo.update_delivery_status(
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
            service_name: The name of the service to update status for
            message: Optional message to include with the status update
        Returns:
            None
        """
        # update service status
        await self._update_delivery_status_internal_async(
            event_id=event_id, status=status, service_name=service_name, message=message
        )

        # Check if the status for all services is "received"
        delivery_status = await self.tranlog_delivery_status_repo.find_by_event_id(event_id=event_id)
        if delivery_status is not None:
            # Check if all services have been received
            all_services_received = all(service.status == "received" for service in delivery_status.services)
            # Check if any service has been received
            any_service_received = any(service.status == "received" for service in delivery_status.services)
            # check if all services have been failed
            all_services_failed = all(service.status == "failed" for service in delivery_status.services)
            if all_services_received:
                # Update overall delivery status to "delivered"
                await self._update_delivery_status_internal_async(event_id=event_id, status="delivered")
            elif any_service_received:
                # Update overall delivery status to "partially_delivered"
                await self._update_delivery_status_internal_async(event_id=event_id, status="partially_delivered")
            elif all_services_failed:
                # Update overall delivery status to "failed"
                await self._update_delivery_status_internal_async(event_id=event_id, status="failed")
        else:
            message = f"Delivery status not found for event_id: {event_id}"
            raise InternalErrorException(message, logger)

    async def republish_undelivered_tranlog_async(self) -> None:
        """
        Republish undelivered transaction logs to the tranlog topic.

        This function retrieves undelivered transaction logs from the database
        and republishes them to the tranlog topic for processing.

        Returns:
            None
        """
        hours_ago = settings.UNDELIVERED_CHECK_PERIOD_IN_HOURS
        undelivered_tranlog_status_list = await self.tranlog_delivery_status_repo.find_pending_deliveries(
            hours_ago=hours_ago
        )
        if not undelivered_tranlog_status_list:
            logger.debug("Don`t worry!  No undelivered tranlogs found")
            return

        logger.warning(f"Undelivered tranlogs found: {len(undelivered_tranlog_status_list)}")

        # Republish undelivered tranlogs
        for status in undelivered_tranlog_status_list:
            # Check if all services have been received
            all_services_received = all(service.status == "received" for service in status.services)
            if all_services_received:
                # Update overall delivery status to "delivered"
                await self._update_delivery_status_internal_async(event_id=status.event_id, status="delivered")
                logger.debug(f"tranlog already delivered: event_id->{status.event_id}")
                continue

            # Check if the tranlog is undelivered shorter than the threshold for skipping
            if status.created_at > datetime.now() - timedelta(minutes=settings.UNDELIVERED_CHECK_INTERVAL_IN_MINUTES):
                # Skip the tranlog if it was created recently
                logger.debug(f"Skipping tranlog: event_id->{status.event_id}")
                continue
            # Check if the tranlog is undelivered longer than the threshold
            failed_minutes = settings.UNDELIVERED_CHECK_FAILED_PERIOD_IN_MINUTES
            if status.created_at < datetime.now() - timedelta(minutes=failed_minutes):
                # Update the delivery status to "failed"
                await self._update_delivery_status_internal_async(event_id=status.event_id, status="failed")
                # notify warning
                await send_warning_notification(
                    message="Undelivered tranlog found: "
                    f"event_id->{status.event_id}, "
                    f"tenant_id->{status.tenant_id}, "
                    f"store_code->{status.store_code}, "
                    f"terminal_no->{status.terminal_no}, "
                    f"transaction_no->{status.transaction_no}",
                    service="cart",
                    context=status.model_dump(),
                )  # Republish the tranlog
            logger.debug(
                f"Republishing tranlog: event_id->{status.event_id}, tenant_id->{status.tenant_id}, transaction_no->{status.transaction_no}"
            )
            await self._publish_tranlog_async(status.payload)

    async def get_transaction_list_with_status_async(
        self, transaction_list: list[BaseTransaction]
    ) -> list[BaseTransaction]:
        """
        Get transaction list with void/return status merged from history.

        This method takes a list of transactions and merges the void/return
        status from the transaction_status collection without modifying
        the original transaction data in the database.

        Args:
            transaction_list: List of transactions to check status for

        Returns:
            List of transactions with is_voided and is_refunded flags updated
        """
        if not transaction_list:
            return transaction_list

        # Extract transaction numbers
        transaction_nos = [tran.transaction_no for tran in transaction_list]

        # Get status for all transactions in one query
        status_dict = await self.transaction_status_repo.get_status_for_transactions_async(
            tenant_id=self.terminal_info.tenant_id,
            store_code=self.terminal_info.store_code,
            terminal_no=self.terminal_info.terminal_no,
            transaction_nos=transaction_nos,
        )

        # Merge status into transaction list
        for tran in transaction_list:
            if tran.transaction_no in status_dict:
                status = status_dict[tran.transaction_no]
                # Update flags in memory only (not in database)
                tran.is_voided = status.is_voided
                tran.is_refunded = status.is_refunded

        return transaction_list

    async def close(self):
        """
        Close the transaction service and cleanup resources.

        This method ensures that all resources are properly cleaned up,
        including closing the pubsub manager which contains HTTP clients.
        """
        if hasattr(self, "pubsub_manager") and self.pubsub_manager:
            await self.pubsub_manager.close()

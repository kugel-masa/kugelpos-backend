# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import sys
from typing import Any
from logging import getLogger
import aiohttp
import uuid
import json
import ast
from datetime import datetime, timedelta

logger = getLogger(__name__)

from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.repositories.store_info_web_repository import StoreInfoWebRepository
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.utils.receipt_numbering import derive_receipt_no, receipt_cycle
from kugel_common.receipt.abstract_receipt_data import AbstractReceiptData
from kugel_common.utils.misc import get_app_time_str, get_app_time
from kugel_common.enums import TransactionType
from kugel_common.utils.slack_notifier import send_warning_notification
from kugel_common.exceptions import DuplicateKeyException

from app.models.repositories.tranlog_repository import TranlogRepository
from app.models.repositories.cart_restore_log_repository import CartRestoreLogRepository
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
from app.services import snapshot_service
from app.exceptions import (
    DocumentNotFoundException,
    BadRequestBodyException,
    StrategyPluginException,
    ExternalServiceException,
    InternalErrorException,
    AlreadyVoidedException,
    AlreadyRefundedException,
    FinalizeConflictException,
    SnapshotInvalidException,
    VoidOutOfSessionException,
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
        store_info_repo: StoreInfoWebRepository = None,
        cart_restore_log_repo: CartRestoreLogRepository = None,
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
        # Where a finalize whose carried numbers do not match the recorded ones
        # is written down (issue #190). Optional: a caller that does not supply
        # it still gets the log line.
        self.cart_restore_log_repo = cart_restore_log_repo
        self.payment_master_repo = payment_master_repo
        # Used to name the store a return is booked into: a return may reference an
        # original from another store (issue #156), so the new transaction must be
        # attributed to the terminal performing it, not to the original's store.
        self.store_info_repo = store_info_repo
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
        # Carry the cart identity into the tranlog so downstream consumers can
        # dedupe a duplicate finalize on cart_id (client-carried cart phase 2,
        # issue #156 / #152).
        tranlog.cart_id = cart.cart_id
        tranlog.tenant_id = self.terminal_info.tenant_id
        tranlog.store_code = self.terminal_info.store_code
        tranlog.store_name = cart.store_name
        tranlog.terminal_no = self.terminal_info.terminal_no
        tranlog.transaction_type = cart.transaction_type
        tranlog.business_date = cart.business_date
        tranlog.open_counter = self.terminal_info.open_counter
        tranlog.business_counter = self.terminal_info.business_counter

        # Client-carried cart phase 2 (issue #156): when the client carries the
        # finalize context (it stamps transaction_datetime at bill), the
        # transaction number, receipt number, and time are taken from the
        # carried values — NOT the server-side counters/clock — so a retried
        # finalize on any backend produces the same number/time/receipt and the
        # downstream cart_id dedupe converges to one record. Without a carried
        # time (legacy / no-snapshot path) the server-side numbering is used.
        carried = cart.transaction_datetime is not None
        # A repeat is reported once. The insert path can report and then fail to
        # commit, which lands in the recovery below - where the tranlog in hand
        # is by then the recorded one, so a second report finds no divergence and
        # says the repeat carried the same numbers, directly after a line saying
        # it carried different ones. The audit row is not at risk; the
        # contradiction in the log is, and that is what a reader works from.
        reported = False
        if carried:
            # (business_counter, seq) composite: transaction_no carries seq.
            tranlog.transaction_no = cart.seq
            tranlog.generate_date_time = cart.transaction_datetime
            tranlog.receipt_counter = cart.receipt_counter
            tranlog.receipt_no = await self._carried_receipt_no_async(cart.receipt_counter, cart.receipt_no)
        else:
            tranlog.transaction_no = await self.terminal_counter_repository.numbering_count(
                countType=CounterType.Transaction.value
            )
            tranlog.generate_date_time = get_app_time_str()
            # The server-side counter is a different series from the terminal's
            # carried one (issue #168), so no receipt_counter is recorded here.
            receipt_start, receipt_end, _ = await self._receipt_range_async()
            tranlog.receipt_no = await self.terminal_counter_repository.numbering_count(
                countType=CounterType.Receipt.value,
                start_value=receipt_start,
                end_value=receipt_end,
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
        # Manual session mgmt (no `async with`): context manager re-aborts after commit ended session — issue #96.
        session = await self.tranlog_repository.start_transaction()
        try:
            self.tranlog_delivery_status_repo.set_session(session)
            await self.tranlog_delivery_status_repo.create_status_async(
                event_id=event_id,
                transaction_no=tranlog.transaction_no,
                payload=event_message,
                services=event_distinations,
            )
            submitted = tranlog
            tranlog = await self.tranlog_repository.create_tranlog_async(tranlog)
            if tranlog is not submitted:
                # Not a fresh insert: the repository returned a tranlog that was
                # already there, so this finalize was a repeat (issue #152).
                await self.__report_finalize_repeat_async(submitted, tranlog, carried)
                reported = True
            await self.tranlog_repository.commit_transaction()

        except FinalizeConflictException:
            # bug_008: the cart_id is already finalized as a DIFFERENT transaction
            # (e.g. a stale-snapshot cancel over a completed sale). Abort the (not
            # yet poisoned) transaction and surface the 409 as-is — do NOT mask it
            # as a 500, and do NOT borrow the unrelated record as an idempotent result.
            await self.tranlog_repository.abort_transaction()
            self.tranlog_repository.set_session(session=None)
            self.tranlog_delivery_status_repo.set_session(session=None)
            raise
        except DuplicateKeyException as e:
            # bug_001: a concurrent identical finalize won the race. Our insert lost
            # on the unique cart_id index and poisoned THIS transaction, so we cannot
            # recover inside it — abort, drop the session, then re-read the winning
            # tranlog in a fresh (non-transaction) session and return it. The finalize
            # is idempotent on cart_id, so the retry observes the same result instead
            # of a 500. The winner already published, so we do NOT publish again.
            existing = await self.__recover_concurrent_finalize(tranlog)
            if existing is not None:
                if not reported:
                    await self.__report_finalize_repeat_async(tranlog, existing, carried)
                    reported = True
                return self.__apply_tranlog_to_cart(cart, existing)
            # The duplicate was on some other unique index (not the cart_id race) —
            # surface it as a real failure.
            message = f"Error creating tranlog: {e}"
            raise InternalErrorException(message, logger) from e
        except Exception as e:
            # The duplicate does not always surface at the insert (issue #172): with
            # two identical finalizes in flight the loser's insert is buffered and
            # the unique index rejects it at COMMIT, so the failure arrives here
            # rather than as a DuplicateKeyException. Same race, same recovery —
            # otherwise the caller is told the transaction failed while the
            # transaction it asked for is sitting in the database.
            existing = await self.__recover_concurrent_finalize(tranlog)
            if existing is not None:
                # Deliberately terse: the exception carries the whole tranlog, and
                # one race must not put a full cart document in the log (issue #155).
                logger.warning(
                    "Finalize failed but the same finalize is already persisted (cart_id=%s, %s); returning it",
                    tranlog.cart_id,
                    type(e).__name__,
                )
                if not reported:
                    await self.__report_finalize_repeat_async(tranlog, existing, carried)
                    reported = True
                return self.__apply_tranlog_to_cart(cart, existing)
            message = f"Error creating tranlog: {e}"
            raise InternalErrorException(message, logger) from e
        finally:
            # clear session
            self.tranlog_repository.set_session(session=None)
            self.tranlog_delivery_status_repo.set_session(session=None)

        # Publish tranlog
        await self._publish_tranlog_async(event_message)

        return self.__apply_tranlog_to_cart(cart, tranlog)

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

    async def get_tranlog_by_transaction_no_async(
        self, store_code: str, terminal_no: int, transaction_no: int, business_counter: int = None
    ):
        """
        Retrieve a specific transaction log by its transaction number.

        Args:
            store_code: Store code where the transaction occurred
            terminal_no: Terminal number where the transaction occurred
            transaction_no: Transaction number (per-open seq in phase 2)
            business_counter: Open epoch of the transaction (issue #156). Together
                with transaction_no this is the transaction's identity; omitted, the
                lookup falls back to the legacy key and raises if it is ambiguous.

        Returns:
            BaseTransaction: The retrieved transaction log

        Raises:
            DocumentNotFoundException: If the transaction is not found
            TransactionAmbiguousException: If transaction_no alone matches several
        """
        tran = await self.tranlog_repository.get_tranlog_by_transaction_no_async(
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            business_counter=business_counter,
        )
        if tran is None:
            message = (
                f"Transaction not found: transaction_no->{transaction_no} "
                f"business_counter->{business_counter} store_code->{store_code} terminal_no->{terminal_no}"
            )
            raise DocumentNotFoundException(message, logger)

        # Merge void/return status from history for single transaction
        transaction_list = await self.get_transaction_list_with_status_async([tran])
        return transaction_list[0] if transaction_list else tran

    async def get_tranlog_for_void_async(
        self, store_code: str, terminal_no: int, transaction_no: int, business_counter: int
    ):
        """
        Resolve the transaction a void is aimed at.

        A void reaches only this terminal's current open session, so the lookup is
        scoped to it. When nothing is found there, "not found" would be a
        misdiagnosis if the number does exist in an earlier session: at the
        register that reads as "you mistyped the receipt", and the operator
        retypes instead of switching to a return. So check, and say which it is.

        Args:
            store_code: Store code of the transaction
            terminal_no: Terminal number of the transaction
            transaction_no: Transaction number (per-open seq in phase 2)
            business_counter: Open epoch to look in

        Returns:
            BaseTransaction: The transaction to void

        Raises:
            VoidOutOfSessionException: The number belongs to another session.
            DocumentNotFoundException: No such transaction anywhere.
        """
        try:
            return await self.get_tranlog_by_transaction_no_async(
                store_code=store_code,
                terminal_no=terminal_no,
                transaction_no=transaction_no,
                business_counter=business_counter,
            )
        except DocumentNotFoundException:
            if not await self.tranlog_repository.exists_in_any_session_async(
                store_code=store_code, terminal_no=terminal_no, transaction_no=transaction_no
            ):
                raise
            message = (
                f"Void is limited to the current open session (business_counter={business_counter}), "
                f"but transaction_no={transaction_no} belongs to an earlier one. Use a return instead."
            )
            raise VoidOutOfSessionException(message, logger)

    async def _resolve_carried_finalize(self, finalize_envelope: dict | None) -> tuple[str, int, int, str]:
        """
        Resolve ``(cart_id, transaction_no, receipt_no, generate_date_time,
        receipt_counter)`` for a
        void/return.

        Client-carried cart phase 2 (issue #156, B案): when the terminal presents a
        signed finalize-context envelope, the void/return draws its **stable**
        ``cart_id`` and its per-open ``seq`` / ``receipt_no`` / time from the
        *verified* carried values. This keeps ``(business_counter, transaction_no)``
        a clean per-open key (the whole open session shares one seq space — sales
        AND void/return) and makes a lost-ACK retry converge on ``cart_id`` (the
        downstream dedupe returns the already-persisted record instead of double
        voiding). Without an envelope the server-side terminal counters assign the
        numbers and a fresh ``cart_id`` is minted (legacy / dual-mode path).

        The envelope scope (tenant/store/terminal) is checked against the
        authenticated terminal, mirroring the cart snapshot path.
        """
        if finalize_envelope is None:
            transaction_no = await self.terminal_counter_repository.numbering_count(CounterType.Transaction.value)
            receipt_start, receipt_end, _ = await self._receipt_range_async()
            receipt_no = await self.terminal_counter_repository.numbering_count(
                CounterType.Receipt.value, start_value=receipt_start, end_value=receipt_end
            )
            # Server-side series: no carried counter to record (issue #168).
            return str(uuid.uuid4()), transaction_no, receipt_no, get_app_time_str(), None

        context = snapshot_service.verify_finalize_context(finalize_envelope)
        if (
            finalize_envelope.get("tenant_id") != self.terminal_info.tenant_id
            or finalize_envelope.get("store_code") != self.terminal_info.store_code
            or finalize_envelope.get("terminal_no") != self.terminal_info.terminal_no
        ):
            raise SnapshotInvalidException(
                f"Finalize-context scope mismatch: "
                f"envelope={finalize_envelope.get('tenant_id')}/{finalize_envelope.get('store_code')}/"
                f"{finalize_envelope.get('terminal_no')}",
                logger,
            )
        cart_id = context.get("cart_id")
        seq = context.get("seq")
        receipt_no = context.get("receipt_no")
        receipt_counter = context.get("receipt_counter")
        transaction_datetime = context.get("transaction_datetime")
        if cart_id is None or seq is None or receipt_no is None or transaction_datetime is None:
            raise SnapshotInvalidException(
                "Finalize-context must carry cart_id, seq, receipt_no and transaction_datetime", logger
            )
        return (
            cart_id,
            seq,
            await self._carried_receipt_no_async(receipt_counter, receipt_no),
            transaction_datetime,
            receipt_counter,
        )

    async def void_async(
        self,
        tran: BaseTransaction,
        add_payment_list: list[dict[str, any]],
        finalize_envelope: dict | None = None,
    ) -> BaseTransaction:
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
        # A void reverses a sale at the register while the drawer and the day's
        # totals are still open. Once the session is settled the correct instrument
        # is a return, which books its own transaction rather than retroactively
        # editing a closed day's figures — so a void is confined to the terminal's
        # current business date AND open session (issue #156). Without this the
        # only thing standing between a caller and an old sale is whether its
        # number happens to be ambiguous, which is not a rule.
        if (
            tran.business_date != self.terminal_info.business_date
            or tran.business_counter != self.terminal_info.business_counter
        ):
            message = (
                f"Void is limited to the current business date and open session: "
                f"transaction business_date={tran.business_date} business_counter={tran.business_counter}, "
                f"terminal business_date={self.terminal_info.business_date} "
                f"business_counter={self.terminal_info.business_counter}. Use a return instead."
            )
            raise VoidOutOfSessionException(message, logger)

        # Check if the transaction has already been voided from history. The epoch
        # is part of the identity (issue #156): transaction_no is the per-open seq,
        # so without it another session's same-numbered sale would be consulted.
        status = await self.transaction_status_repo.get_status_by_transaction_async(
            tran.tenant_id, tran.store_code, tran.terminal_no, tran.transaction_no, tran.business_counter
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
        # The original's open epoch: transaction_no is the per-open seq (issue
        # #156), so the origin only names one transaction together with this.
        tran.origin.business_counter = tran.business_counter
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

        # The void is its own transaction with its OWN cart_id (issue #156): never
        # inherit the original sale's cart_id (downstream dedupe would skip the
        # void, leaving the sale counted and inventory never reversed). On the
        # stateless path the terminal carries a stable cart_id + per-open seq /
        # receipt_no / time in a signed envelope (retry converges, numbering stays
        # a clean per-open sequence); legacy mints a fresh cart_id + server numbers.
        (
            tran.cart_id,
            tran.transaction_no,
            tran.receipt_no,
            tran.generate_date_time,
            tran.receipt_counter,
        ) = await self._resolve_carried_finalize(finalize_envelope)
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
        # Manual session mgmt (no `async with`): context manager re-aborts after commit ended session — issue #96.
        session = await self.tranlog_repository.start_transaction()
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
            business_counter=tran.origin.business_counter,
            void_transaction_no=tran.transaction_no,
            staff_id=tran.staff.id,
        )

        # If we're voiding a return transaction, reset the refund status on the original sale
        if tran.transaction_type == TransactionType.VoidReturn.value:
            # The origin contains the return transaction info
            # We need to find the original sale transaction that was refunded
            return_tran = await self.tranlog_repository.get_one_async(
                {
                    "tenant_id": tran.origin.tenant_id,
                    "store_code": tran.origin.store_code,
                    "terminal_no": tran.origin.terminal_no,
                    "transaction_no": tran.origin.transaction_no,
                }
            )

            if return_tran and return_tran.origin:
                # Reset the refund status on the original sale transaction
                await self.transaction_status_repo.reset_refund_status_async(
                    tenant_id=return_tran.origin.tenant_id,
                    store_code=return_tran.origin.store_code,
                    terminal_no=return_tran.origin.terminal_no,
                    transaction_no=return_tran.origin.transaction_no,
                    business_counter=return_tran.origin.business_counter,
                )

        return tran

    async def __get_own_store_name_async(self, fallback: str = None) -> str:
        """
        Resolve the name of the store this terminal belongs to.

        Used when a return is attributed to the performing terminal rather than to
        the original transaction's store (issue #156). Returns the fallback when
        the store repository is unavailable or the lookup fails — naming the store
        is presentation detail and must not fail the return. Callers on the return
        path pass no fallback on purpose: the only other name available is the
        original transaction's, and pairing it with this terminal's store_code
        would misattribute the receipt.

        Args:
            fallback: Value to use when the lookup cannot be performed

        Returns:
            str: The store name, or the fallback
        """
        if self.store_info_repo is None:
            return fallback
        try:
            store_info = await self.store_info_repo.get_store_info_async()
            return store_info.store_name if store_info else fallback
        except Exception as e:
            logger.warning(f"Failed to resolve own store name; keeping {fallback}: {e}")
            return fallback

    async def return_async(
        self,
        tran: BaseTransaction,
        add_payment_list: list[dict[str, any]],
        finalize_envelope: dict | None = None,
    ) -> BaseTransaction:
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
        # Check if the transaction has already been refunded or voided from history.
        # The epoch is part of the identity (issue #156) — see void_async.
        status = await self.transaction_status_repo.get_status_by_transaction_async(
            tran.tenant_id, tran.store_code, tran.terminal_no, tran.transaction_no, tran.business_counter
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
        # The original's open epoch: transaction_no is the per-open seq (issue
        # #156), so the origin only names one transaction together with this.
        tran.origin.business_counter = tran.business_counter
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
        # The return is its own transaction with its OWN cart_id (issue #156): on
        # the stateless path the terminal carries a stable cart_id + per-open seq /
        # receipt_no / time in a signed envelope (retry converges, numbering stays a
        # clean per-open sequence); legacy mints a fresh cart_id + server numbers.
        (
            tran.cart_id,
            tran.transaction_no,
            tran.receipt_no,
            tran.generate_date_time,
            tran.receipt_counter,
        ) = await self._resolve_carried_finalize(finalize_envelope)
        tran.sales.reference_date_time = tran.generate_date_time
        tran.sales.change_amount = 0  # change amount is not applicable for return transaction
        # The return belongs to the terminal performing it, not to the original's
        # store/terminal (issue #156): a return may reference an original from
        # another terminal or another store, and `tran` here is the ORIGINAL
        # document being rewritten in place. Without this the return would be
        # booked against the original's store/terminal while carrying this
        # terminal's business_counter/seq — a numbering tuple that belongs to
        # neither, colliding with the other terminal's own sequence.
        tran.store_code = self.terminal_info.store_code
        # Deliberately no fallback to the original's name: keeping it would pair
        # this terminal's store_code with another store's store_name and print
        # that on the receipt. An empty name is the lesser wrong.
        tran.store_name = await self.__get_own_store_name_async()
        tran.terminal_no = self.terminal_info.terminal_no
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
        # Manual session mgmt (no `async with`): context manager re-aborts after commit ended session — issue #96.
        session = await self.tranlog_repository.start_transaction()
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
            business_counter=tran.origin.business_counter,
            return_transaction_no=tran.transaction_no,
            staff_id=tran.staff.id,
        )

        return tran

    # The finalize context a terminal carries (issue #156). What a repeat claims
    # for these is the whole question issue #190 is about.
    CARRIED_FINALIZE_FIELDS = ("transaction_no", "receipt_no", "receipt_counter", "generate_date_time")

    @staticmethod
    def __same_instant(asked, holds) -> bool:
        """Whether two stamped times are the same moment, however they are written.

        The carried value is validated as ISO-8601 but not normalised, so the same
        instant can arrive as `...+00:00` or `...Z`, with or without microseconds.
        Comparing the strings would report those as a terminal that had moved on.
        """
        if asked == holds:
            return True
        if not isinstance(asked, str) or not isinstance(holds, str):
            return False
        try:
            return datetime.fromisoformat(asked.replace("Z", "+00:00")) == datetime.fromisoformat(
                holds.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return False

    def __finalize_divergence(self, carried: BaseTransaction, recorded: BaseTransaction) -> dict:
        """What this finalize asked to record that differs from what is recorded."""
        divergence = {}
        for field in self.CARRIED_FINALIZE_FIELDS:
            asked, holds = getattr(carried, field, None), getattr(recorded, field, None)
            if field == "generate_date_time" and self.__same_instant(asked, holds):
                continue
            if asked != holds:
                divergence[field] = {"carried": asked, "recorded": holds}
        return divergence

    async def __report_finalize_repeat_async(
        self, carried: BaseTransaction, recorded: BaseTransaction, client_numbered: bool = True
    ) -> None:
        """
        Write down that a finalize repeated, and whether it repeated itself (issue #190).

        A terminal repeats because it did not hear the first answer, and it is
        answered with the transaction that exists - which is right, and which the
        log already said. What it did not say is whether the repeat carried the
        SAME numbers.

        It usually does: a terminal that heard nothing has not advanced. When it
        does not, the terminal's running receipt counter has moved past what was
        recorded, and that means one of three things - it printed a receipt whose
        number is in no transaction log, or it advanced without printing (a gap,
        which issue #166 allows), or a different transaction reused the cart_id.
        The first is worth chasing and the second is not, and until now they left
        the same single line behind.
        """
        # Only when the terminal supplied the numbers. On the server-numbered
        # path the numbers in hand were issued by this request from the server's
        # own counter and clock, so a race against a concurrent finalize differs
        # by construction - measured at "carried 50 vs recorded 49" for two
        # simultaneous bills - and says nothing at all about the terminal. Filing
        # that would bury the rows that do mean something.
        divergence = self.__finalize_divergence(carried, recorded) if client_numbered else {}
        if not divergence:
            logger.warning(
                "Finalize repeated for cart_id=%s carrying the same numbers; "
                "answered with the transaction already recorded",
                recorded.cart_id,
            )
            return

        logger.error(
            "Finalize repeated for cart_id=%s carrying DIFFERENT numbers (issue #190): %s. "
            "The terminal has moved past what is recorded; a printed receipt may carry a "
            "number that appears in no transaction log.",
            recorded.cart_id,
            divergence,
        )
        if self.cart_restore_log_repo is None:
            return
        try:
            await self.cart_restore_log_repo.add_record_async(
                result="finalize_repeat_diverged",
                cart_id=recorded.cart_id,
                diverged=True,
                reject_reason=", ".join(
                    f"{field}: carried {values['carried']} vs recorded {values['recorded']}"
                    for field, values in divergence.items()
                ),
            )
        except Exception as e:
            # The transaction is recorded and answered; losing the note about it
            # must not turn that into a failure.
            logger.error(f"Could not record the finalize divergence for cart_id={recorded.cart_id}: {e}")

    def __apply_tranlog_to_cart(self, cart: CartDocument, tranlog: BaseTransaction) -> BaseTransaction:
        """
        Copy the finalized transaction's identity onto the cart the caller holds.

        The response is built from the cart, so this has to happen on the
        recovery path too (issue #172): a caller that lost a concurrent finalize
        race is handed the winner's tranlog, and without this its cart would
        still carry no receipt_no and the response would fail validation.

        Args:
            cart: The cart document being finalized
            tranlog: The persisted transaction log

        Returns:
            The transaction log, so callers can `return` this directly
        """
        cart.transaction_no = tranlog.transaction_no
        cart.receipt_no = tranlog.receipt_no
        cart.staff = tranlog.staff
        cart.receipt_text = tranlog.receipt_text
        cart.journal_text = tranlog.journal_text
        return tranlog

    async def __recover_concurrent_finalize(self, tranlog: BaseTransaction) -> BaseTransaction:
        """
        The tranlog a concurrent request already wrote for this finalize, if any.

        Called after a failed finalize (issue #156 bug_001, issue #172). The
        transaction is poisoned, so recovery cannot happen inside it: abort it,
        drop the session, and look the record up in a fresh one. Returning it is
        idempotent — the winner already published, so the caller must not publish
        again.

        Args:
            tranlog: The transaction log this attempt was writing

        Returns:
            The persisted tranlog for the same finalize, or None when no
            concurrent request wrote one (i.e. the failure was something else)

        Raises:
            FinalizeConflictException: The cart_id belongs to a different
                finalize, which must surface as a 409 rather than a 500.
        """
        await self.tranlog_repository.abort_transaction()
        self.tranlog_repository.set_session(session=None)
        self.tranlog_delivery_status_repo.set_session(session=None)

        existing = await self.tranlog_repository.get_existing_finalize_async(tranlog)
        if existing is not None:
            logger.warning(
                f"Concurrent finalize race for cart_id={tranlog.cart_id}; returning the winning tranlog idempotently"
            )
        return existing

    async def _receipt_range_async(self) -> tuple:
        """
        Resolve the configured printed receipt-number range for this terminal.

        Settings come back as strings (master-data /settings/{name}/value returns
        the value as-is), and the server-side counter increment uses MongoDB's
        $add aggregation which fails with TypeMismatch on non-numeric operands,
        so both ends are cast here.

        The lookup is a cached master-data read that degrades to None when the
        cache misses and master-data is unreachable, so the caller is told
        whether the range it received is the configured one or the unbounded
        fallback - printing a number outside the configured range is a visible
        defect and must not pass silently.

        Returns:
            Tuple of (start_value, end_value, resolved) where `resolved` is False
            when either end fell back to its default
        """
        start_raw = await self._get_setting_value_async("RECEIPT_NO_START_VALUE")
        end_raw = await self._get_setting_value_async("RECEIPT_NO_END_VALUE")
        resolved = start_raw is not None and end_raw is not None
        start = int(start_raw) if start_raw is not None else 1
        end = int(end_raw) if end_raw is not None else sys.maxsize
        return start, end, resolved

    async def _carried_receipt_no_async(self, receipt_counter: int, carried_receipt_no: int) -> int:
        """
        Printed receipt number for a client-carried finalize (issue #166).

        Derived from the carried running counter and the configured range, so a
        terminal that wraps prints inside the range instead of counting 1, 2, 3.

        The client printed its own number on paper before the backend ever saw
        the transaction, so a carried number wins over the derived one; a
        mismatch means the two disagree about the range (a setting changed
        mid-session) and is reported rather than silently corrected.

        A pre-#166 client carries no counter at all; its number is taken as-is,
        which is the phase 2 behaviour this issue is fixing.

        Args:
            receipt_counter: Carried running receipt counter, None for pre-#166 clients
            carried_receipt_no: Receipt number the client printed, if any

        Returns:
            The receipt number to record on the transaction log
        """
        if receipt_counter is None:
            return carried_receipt_no

        start, end, resolved = await self._receipt_range_async()
        if not resolved:
            # The range is what maps the counter into printable territory. Without
            # it the derived number would leave the configured range entirely, so
            # prefer whatever the terminal printed and say so loudly.
            logger.error(
                "Receipt number range unavailable (counter=%s); %s. Check master-data reachability.",
                receipt_counter,
                (
                    "recording the number the terminal printed"
                    if carried_receipt_no is not None
                    else "recording the raw counter, which is outside the configured range"
                ),
            )
            return carried_receipt_no if carried_receipt_no is not None else receipt_counter

        try:
            derived = derive_receipt_no(receipt_counter, start, end)
        except ValueError as e:
            # Misconfigured range: keep the number the customer holds.
            logger.error("Cannot derive receipt_no (counter=%s): %s", receipt_counter, e)
            return carried_receipt_no

        if carried_receipt_no is not None and carried_receipt_no != derived:
            logger.warning(
                "Carried receipt_no %s does not match the configured range "
                "(counter=%s cycle=%s range=%s..%s derives %s); recording the carried "
                "value, which is what the customer received",
                carried_receipt_no,
                receipt_counter,
                receipt_cycle(receipt_counter, start, end),
                start,
                end,
                derived,
            )
            return carried_receipt_no
        return derived

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

        # A status record is identified by (store, terminal, open epoch,
        # transaction_no) — issue #156. The list is normally one terminal's own
        # transactions, but a single-transaction lookup may name another store's
        # (a return can reference an original rung up anywhere in the tenant), so
        # group by the owning identity instead of assuming this terminal's.
        groups: dict[tuple, list[int]] = {}
        for tran in transaction_list:
            groups.setdefault((tran.store_code, tran.terminal_no, tran.business_counter), []).append(
                tran.transaction_no
            )

        status_by_identity = {}
        for (store_code, terminal_no, business_counter), transaction_nos in groups.items():
            status_dict = await self.transaction_status_repo.get_status_for_transactions_async(
                tenant_id=self.terminal_info.tenant_id,
                store_code=store_code,
                terminal_no=terminal_no,
                transaction_nos=transaction_nos,
                business_counter=business_counter,
            )
            for transaction_no, status in status_dict.items():
                status_by_identity[(store_code, terminal_no, business_counter, transaction_no)] = status

        # Merge status into transaction list
        for tran in transaction_list:
            status = status_by_identity.get(
                (tran.store_code, tran.terminal_no, tran.business_counter, tran.transaction_no)
            )
            if status is not None:
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

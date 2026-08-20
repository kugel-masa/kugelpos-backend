# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase

from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.exceptions import CannotCreateException, DuplicateKeyException
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.schemas.pagination import PaginatedResult
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.config.settings import settings
from app.exceptions import FinalizeConflictException, TransactionAmbiguousException

logger = getLogger(__name__)


class TranlogRepository(AbstractRepository[BaseTransaction]):
    """
    Repository for managing transaction logs.

    This class provides methods to create, query, and retrieve transaction log records
    from the database. Transaction logs represent completed transactions in the system,
    providing a history of all sales and other transaction activities.
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Initialize the repository with database connection and terminal information.

        Args:
            db: Database connection object
            terminal_info: Terminal information document containing tenant, store, and terminal details
        """
        super().__init__(settings.DB_COLLECTION_NAME_TRAN_LOG, BaseTransaction, db)
        self.terminal_info = terminal_info

    async def create_tranlog_async(self, tranlog: BaseTransaction) -> BaseTransaction:
        """
        Create a new transaction log entry in the database.

        Sets the appropriate shard key before saving the transaction log to ensure
        proper data partitioning.

        Args:
            tranlog: Transaction log document to create

        Returns:
            BaseTransaction: The created transaction log document

        Raises:
            CannotCreateException: If the transaction log could not be created
        """
        try:
            # Idempotent finalize pre-check (issue #156): a lost-ACK retry of the
            # same finalize carries the same cart_id. Return the already-persisted
            # tranlog BEFORE attempting the insert — the insert runs inside the
            # finalize transaction, and letting the duplicate hit the unique index
            # would abort that transaction (and recovery-within-it would fail).
            if tranlog.cart_id is not None:
                existing = await self.get_one_async(
                    {
                        "tenant_id": tranlog.tenant_id,
                        "store_code": tranlog.store_code,
                        "cart_id": tranlog.cart_id,
                    }
                )
                if existing is not None:
                    # Only a genuine retry of the SAME finalize is idempotent.
                    # A DIFFERENT operation reusing this cart_id (e.g. a stale
                    # EnteringItem snapshot replayed as a Cancel over a Completed
                    # sale) must NOT borrow the existing record's result — that
                    # would silently swallow the new op while reporting success
                    # (bug_008). Require the operation identity to match.
                    if self.__is_same_finalize(existing, tranlog):
                        logger.warning(f"Idempotent finalize: tranlog for cart_id={tranlog.cart_id} already exists")
                        return existing
                    message = (
                        f"cart_id={tranlog.cart_id} already finalized as a different transaction "
                        f"(existing type={existing.transaction_type}, cancelled={self.__is_cancelled(existing)}; "
                        f"incoming type={tranlog.transaction_type}, cancelled={self.__is_cancelled(tranlog)})"
                    )
                    raise FinalizeConflictException(message, logger)

            tranlog.shard_key = self.__get_shard_key(tranlog)
            logger.debug(f"TranlogRepository.create_tranlog_async: tranlog->{tranlog}")
            if not await self.create_async(tranlog):
                raise Exception()
            return tranlog
        except (DuplicateKeyException, FinalizeConflictException):
            # bug_001: a concurrent identical finalize won the race — our insert
            # lost on the unique cart_id index. Propagate the DuplicateKeyException
            # so the caller (which owns the finalize transaction) can abort it and
            # re-read the winner's tranlog idempotently in a fresh session; recovery
            # cannot happen here because the transaction is already poisoned.
            # FinalizeConflictException is a deliberate 409 and must not be masked.
            raise
        except Exception as e:
            message = (
                "Failed to create tranlog: "
                f"tenant_id->{self.terminal_info.tenant_id} "
                f"store_code->{self.terminal_info.store_code} "
                f"terminal_no->{self.terminal_info.terminal_no} "
                f"transaction_no->{tranlog.transaction_no} "
                f"transaction_type->{tranlog.transaction_type}"
            )
            raise CannotCreateException(message, logger, e) from e

    async def get_tranlog_by_transaction_no_async(
        self, store_code: str, terminal_no: int, transaction_no: int, business_counter: int = None
    ) -> BaseTransaction:
        """
        Retrieve a specific transaction log by its transaction number.

        Client-carried cart phase 2 (issue #156): transaction_no is the per-open
        seq and repeats every open session, so the transaction is only pinned down
        together with ``business_counter`` — the same tuple the unique index uses.
        Callers that supply it get an exact match.

        When it is omitted (legacy clients, and transactions numbered by the
        server before phase 2) the lookup falls back to the old key. That key can
        now match several documents, and picking one arbitrarily would void or
        refund a different sale than the one on the receipt — so an ambiguous
        match raises instead of guessing.

        Args:
            store_code: Store code where the transaction occurred
            terminal_no: Terminal number where the transaction occurred
            transaction_no: Transaction number (per-open seq in phase 2)
            business_counter: Open epoch of the transaction; None falls back to
                the legacy key with an ambiguity guard

        Returns:
            BaseTransaction: The retrieved transaction log, or None if not found

        Raises:
            TransactionAmbiguousException: The legacy key matched more than one
                transaction, so business_counter is required to disambiguate.
        """
        query = {
            "tenant_id": self.terminal_info.tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": transaction_no,
        }
        if business_counter is not None:
            query["business_counter"] = business_counter
            logger.debug(f"TranlogRepository.get_tranlog_by_transaction_no_async: query->{query}")
            return await self.get_one_async(query)

        logger.debug(f"TranlogRepository.get_tranlog_by_transaction_no_async (no epoch): query->{query}")
        # Read two: one row is unambiguous, two means the caller must say which
        # open session it meant.
        matches = await self.get_list_async(filter=query, max=2)
        if not matches:
            return None
        if len(matches) > 1:
            message = (
                f"transaction_no={transaction_no} matches {len(matches)}+ transactions on "
                f"store_code={store_code} terminal_no={terminal_no} "
                f"(business_counters include {[m.business_counter for m in matches]}). "
                "Specify business_counter to identify the transaction."
            )
            raise TransactionAmbiguousException(message, logger)
        return matches[0]

    async def exists_in_any_session_async(self, store_code: str, terminal_no: int, transaction_no: int) -> bool:
        """
        Whether a transaction with this number exists in ANY open session.

        Used to tell "the number is wrong" apart from "the number is right but the
        sale belongs to a session this operation cannot reach" (issue #156). The
        two need different answers at the register: one means re-read the receipt,
        the other means use a return instead.

        Args:
            store_code: Store code where the transaction occurred
            terminal_no: Terminal number where the transaction occurred
            transaction_no: Transaction number (per-open seq in phase 2)

        Returns:
            bool: True if at least one transaction carries this number
        """
        query = {
            "tenant_id": self.terminal_info.tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": transaction_no,
        }
        return await self.get_one_async(query) is not None

    # get tranlog list by query parameters
    async def get_tranlog_list_by_query_async(
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
    ) -> PaginatedResult[BaseTransaction]:
        """
        Retrieve a paginated list of transaction logs matching the specified criteria.

        Args:
            store_code: Store code filter
            terminal_no: Terminal number filter
            business_date: Optional business date filter (format: YYYY-MM-DD)
            open_counter: Optional open counter number filter
            transaction_type: Optional list of transaction types to include
            receipt_no: Optional receipt number filter
            limit: Maximum number of records to return per page
            page: Page number to retrieve
            sort: List of field name and direction tuples for sorting
            include_cancelled: Whether to include cancelled transactions

        Returns:
            PaginatedResult[BaseTransaction]: Paginated list of matching transaction logs
        """
        query = {"tenant_id": self.terminal_info.tenant_id, "store_code": store_code, "terminal_no": terminal_no}
        if business_date:
            query["business_date"] = business_date
        if open_counter:
            query["open_counter"] = open_counter
        if transaction_type:
            query["transaction_type"] = {"$in": transaction_type}
        if receipt_no:
            query["receipt_no"] = receipt_no
        if not include_cancelled:
            query["sales.is_cancelled"] = False
        logger.debug(
            f"TranlogRepository.get_tranlog_list_by_query_async: query->{query} limit->{limit} page->{page} sort->{sort}"
        )
        return await self.get_paginated_list_async(filter=query, limit=limit, page=page, sort=sort)

    @staticmethod
    def __is_cancelled(tranlog: BaseTransaction) -> bool:
        """Whether the tranlog represents a cancelled sale (sales.is_cancelled)."""
        sales = getattr(tranlog, "sales", None)
        return bool(getattr(sales, "is_cancelled", False)) if sales is not None else False

    def __is_same_finalize(self, existing: BaseTransaction, incoming: BaseTransaction) -> bool:
        """
        Decide whether an already-persisted tranlog is the SAME finalize operation
        as the incoming one (a true idempotent retry) versus a different operation
        that happens to reuse the cart_id (issue #156 / bug_008).

        The operation identity is (transaction_type, is_cancelled): a Cancel and a
        normal Sale of the same cart share transaction_type but differ on
        sales.is_cancelled, so both must be compared.
        """
        return (
            existing.transaction_type == incoming.transaction_type
            and self.__is_cancelled(existing) == self.__is_cancelled(incoming)
        )

    def __get_shard_key(self, tranlog: BaseTransaction) -> str:
        """
        Generate a shard key for partitioning transaction log data.

        Creates a shard key based on tenant ID, store code, terminal number, and
        the date portion of the generation timestamp.

        Args:
            tranlog: The transaction log document

        Returns:
            str: The generated shard key
        """
        key = []
        key.append(tranlog.tenant_id)
        key.append(tranlog.store_code)
        key.append(str(tranlog.terminal_no))
        key.append(tranlog.generate_date_time.split("T")[0])  # format: YYYY-MM-DDTHH:MM:SSZ
        return self.make_shard_key(key)

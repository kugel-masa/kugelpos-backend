# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Repository for transaction status tracking
"""
from typing import Optional, List, Dict
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.transaction_status_document import TransactionStatusDocument
from kugel_common.utils.misc import get_app_time_str
from app.config.settings import settings

logger = getLogger(__name__)


class TransactionStatusRepository(AbstractRepository[TransactionStatusDocument]):
    """
    Repository for managing transaction void/return status
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Initialize the repository

        Args:
            db: MongoDB database connection instance
            terminal_info: Terminal information document
        """
        super().__init__(settings.DB_COLLECTION_NAME_STATUS_TRAN, TransactionStatusDocument, db)
        self.terminal_info = terminal_info

    async def get_status_by_transaction_async(
        self, tenant_id: str, store_code: str, terminal_no: int, transaction_no: int
    ) -> Optional[TransactionStatusDocument]:
        """
        Get transaction status by transaction identifiers
        """
        query = {
            "tenant_id": tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": transaction_no,
        }
        return await self.get_one_async(query)

    async def mark_as_voided_async(
        self,
        tenant_id: str,
        store_code: str,
        terminal_no: int,
        transaction_no: int,
        void_transaction_no: int,
        staff_id: str,
    ) -> TransactionStatusDocument:
        """
        Mark a transaction as voided
        """
        # Check if status document already exists
        existing = await self.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)

        current_time = get_app_time_str()

        if existing:
            # Update existing document
            update_values = {
                "is_voided": True,
                "void_transaction_no": void_transaction_no,
                "void_date_time": current_time,
                "void_staff_id": staff_id,
            }

            # Preserve existing refund info if present
            if existing.is_refunded:
                update_values["is_refunded"] = existing.is_refunded
                if existing.return_transaction_no is not None:
                    update_values["return_transaction_no"] = existing.return_transaction_no
                if existing.return_date_time is not None:
                    update_values["return_date_time"] = existing.return_date_time
                if existing.return_staff_id is not None:
                    update_values["return_staff_id"] = existing.return_staff_id

            # Update the document using the same filter as get_status_by_transaction_async
            filter_dict = {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "terminal_no": terminal_no,
                "transaction_no": transaction_no,
            }
            await self.update_one_async(filter_dict, update_values)

            # Return updated document
            return await self.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)
        else:
            # Create new status document
            status_doc = TransactionStatusDocument(
                tenant_id=tenant_id,
                store_code=store_code,
                terminal_no=terminal_no,
                transaction_no=transaction_no,
                is_voided=True,
                void_transaction_no=void_transaction_no,
                void_date_time=current_time,
                void_staff_id=staff_id,
            )

            await self.create_async(status_doc)
            return status_doc

    async def mark_as_refunded_async(
        self,
        tenant_id: str,
        store_code: str,
        terminal_no: int,
        transaction_no: int,
        return_transaction_no: int,
        staff_id: str,
    ) -> TransactionStatusDocument:
        """
        Mark a transaction as refunded
        """
        # Check if status document already exists
        existing = await self.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)

        current_time = get_app_time_str()

        if existing:
            # Update existing document
            update_values = {
                "is_refunded": True,
                "return_transaction_no": return_transaction_no,
                "return_date_time": current_time,
                "return_staff_id": staff_id,
            }

            # Preserve existing void info if present
            if existing.is_voided:
                update_values["is_voided"] = existing.is_voided
                if existing.void_transaction_no is not None:
                    update_values["void_transaction_no"] = existing.void_transaction_no
                if existing.void_date_time is not None:
                    update_values["void_date_time"] = existing.void_date_time
                if existing.void_staff_id is not None:
                    update_values["void_staff_id"] = existing.void_staff_id

            # Update the document using the same filter as get_status_by_transaction_async
            filter_dict = {
                "tenant_id": tenant_id,
                "store_code": store_code,
                "terminal_no": terminal_no,
                "transaction_no": transaction_no,
            }
            await self.update_one_async(filter_dict, update_values)

            # Return updated document
            return await self.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)
        else:
            # Create new status document
            status_doc = TransactionStatusDocument(
                tenant_id=tenant_id,
                store_code=store_code,
                terminal_no=terminal_no,
                transaction_no=transaction_no,
                is_refunded=True,
                return_transaction_no=return_transaction_no,
                return_date_time=current_time,
                return_staff_id=staff_id,
            )

            await self.create_async(status_doc)
            return status_doc

    async def get_status_for_transactions_async(
        self, tenant_id: str, store_code: str, terminal_no: int, transaction_nos: List[int]
    ) -> Dict[int, TransactionStatusDocument]:
        """
        Get status for multiple transactions
        Returns a dictionary with transaction_no as key
        """
        query = {
            "tenant_id": tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": {"$in": transaction_nos},
        }

        status_list = await self.get_list_async(query)

        # Convert to dictionary for easy lookup
        status_dict = {}
        for status in status_list:
            status_dict[status.transaction_no] = status

        return status_dict

    async def reset_refund_status_async(
        self, tenant_id: str, store_code: str, terminal_no: int, transaction_no: int
    ) -> Optional[TransactionStatusDocument]:
        """
        Reset the refund status of a transaction.
        This is used when a return transaction is voided.
        """
        # Check if status document exists
        existing = await self.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)

        if not existing:
            # No status document exists, nothing to reset
            return None

        # Update values to clear refund information
        update_values = {
            "is_refunded": False,
            "return_transaction_no": None,
            "return_date_time": None,
            "return_staff_id": None,
        }

        # Update the document
        filter_dict = {
            "tenant_id": tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": transaction_no,
        }
        await self.update_one_async(filter_dict, update_values)

        # Return updated document
        return await self.get_status_by_transaction_async(tenant_id, store_code, terminal_no, transaction_no)

# Copyright 2026 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Repository for the cart restore audit trail (issue #148)
"""

from typing import Optional
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.misc import get_app_time_str
from app.models.documents.cart_restore_log_document import CartRestoreLogDocument
from app.config.settings import settings

logger = getLogger(__name__)


class CartRestoreLogRepository(AbstractRepository[CartRestoreLogDocument]):
    """
    Writes one audit record per restore attempt (success or rejection).

    Audit writes are best-effort for rejections triggered before any state
    change, but a restore that mutates state must be recorded; callers decide
    whether a failed audit write fails the operation.
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Args:
            db: MongoDB database connection instance (tenant database)
            terminal_info: Authenticated terminal information (requesting side)
        """
        super().__init__(settings.DB_COLLECTION_NAME_LOG_CART_RESTORE, CartRestoreLogDocument, db)
        self.terminal_info = terminal_info

    async def add_record_async(
        self,
        result: str,
        cart_id: Optional[str] = None,
        reject_reason: Optional[str] = None,
        diverged: bool = False,
        api_path: Optional[str] = None,
        snapshot_issued_at: Optional[str] = None,
        snapshot_terminal_no: Optional[int] = None,
        snapshot_kid: Optional[str] = None,
        snapshot_schema_version: Optional[int] = None,
        snapshot_revision: Optional[int] = None,
    ) -> CartRestoreLogDocument:
        """
        Append one restore/snapshot-event audit record for the terminal.

        Args:
            result: "restored" / "existing_returned" / "rejected"
            cart_id: Target cart id from the snapshot, when parseable
            reject_reason: Cart error code on rejection (e.g. "401501")
            diverged: True when the snapshot differs from an existing cart
            api_path: API path of the event (issue #156); None for restore
            snapshot_*: Metadata extracted from the presented envelope
        """
        record = CartRestoreLogDocument(
            tenant_id=self.terminal_info.tenant_id,
            store_code=self.terminal_info.store_code,
            terminal_no=self.terminal_info.terminal_no,
            cart_id=cart_id,
            result=result,
            reject_reason=reject_reason,
            diverged=diverged,
            api_path=api_path,
            snapshot_issued_at=snapshot_issued_at,
            snapshot_terminal_no=snapshot_terminal_no,
            snapshot_kid=snapshot_kid,
            snapshot_schema_version=snapshot_schema_version,
            snapshot_revision=snapshot_revision,
            event_datetime=get_app_time_str(),
        )
        await self.create_async(record)
        return record

    async def get_by_cart_id_async(self, cart_id: str) -> list[CartRestoreLogDocument]:
        """Return all restore audit records for a cart in insertion order."""
        return await self.get_list_async({"cart_id": cart_id})

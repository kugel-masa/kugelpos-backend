# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
TerminallogDeliveryStatus repository module

This module provides repository classes for managing terminal log delivery statuses.
It handles storing, retrieving, and updating the delivery status of terminal logs.
"""
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from datetime import datetime, timedelta, timezone

from kugel_common.utils.misc import get_app_time
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.terminallog_delivery_status_document import TerminallogDeliveryStatus
from app.config.settings import settings

logger = getLogger(__name__)


class TerminallogDeliveryStatusRepository(AbstractRepository[TerminallogDeliveryStatus]):
    """
    Terminal Log Delivery Status Repository

    A repository for managing terminal log delivery statuses,
    extending AbstractRepository and providing specific implementation
    for MongoDB operations related to terminal log delivery tracking.
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Initialize the repository

        Args:
            db: MongoDB database connection instance
            terminal_info: Terminal information document
        """
        super().__init__(settings.DB_COLLECTION_NAME_TERMINALLOG_DELIVERY_STATUS, TerminallogDeliveryStatus, db)
        self.terminal_info = terminal_info

    async def create_status_async(
        self,
        event_id: str,
        payload: dict,
        services: List[dict] = None,
        terminal_info: Optional[TerminalInfoDocument] = None,
    ) -> bool:
        """
        Create a new delivery status document

        Args:
            event_id: Event ID (UUID)
            payload: Message payload
            services: List of service dictionaries

        Returns:
            bool: True if creation was successful, False otherwise

        Raises:
            DuplicateKeyException: If a document with the same key already exists
            RepositoryException: If any other database error occurs
        """
        now = get_app_time()

        if terminal_info is None:
            terminal_info = self.terminal_info
        tenant_id = terminal_info.tenant_id
        store_code = terminal_info.store_code
        terminal_no = terminal_info.terminal_no
        business_date = terminal_info.business_date
        open_counter = terminal_info.open_counter

        # Process service information
        service_status_list = []
        if services:
            for service in services:
                service_status = TerminallogDeliveryStatus.ServiceStatus(
                    service_name=service.get("service_name"), status=service.get("status", "pending")
                )
                service_status_list.append(service_status)

        # Create document
        terminallog_delivery_status = TerminallogDeliveryStatus(
            event_id=event_id,
            published_at=now,
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            business_date=business_date,
            open_counter=open_counter,
            payload=payload,
            services=service_status_list,
            status="published",
            last_updated_at=now,
        )

        # Save to database
        return await self.create_async(terminallog_delivery_status)

    async def find_by_event_id(self, event_id: str) -> Optional[TerminallogDeliveryStatus]:
        """
        Find delivery status by event ID

        Args:
            event_id: Event ID to search for

        Returns:
            TerminallogDeliveryStatus: Matching document if found, None otherwise
        """
        return await self.get_one_async({"event_id": event_id})

    async def find_by_terminal_info(
        self, tenant_id: str, store_code: str, terminal_no: int
    ) -> List[TerminallogDeliveryStatus]:
        """
        Find delivery statuses by terminal information

        Args:
            tenant_id: Tenant ID
            store_code: Store code
            terminal_no: Terminal number

        Returns:
            List[TerminallogDeliveryStatus]: List of matching delivery status documents
        """
        filter_dict = {"tenant_id": tenant_id, "store_code": store_code, "terminal_no": terminal_no}
        return await self.get_list_async(filter_dict)

    async def find_by_business_date(
        self, tenant_id: str, store_code: str, business_date: str
    ) -> List[TerminallogDeliveryStatus]:
        """
        Find delivery statuses by business date

        Args:
            tenant_id: Tenant ID
            store_code: Store code
            business_date: Business date (YYYYMMDD format)

        Returns:
            List[TerminallogDeliveryStatus]: List of matching delivery status documents
        """
        filter_dict = {"tenant_id": tenant_id, "store_code": store_code, "business_date": business_date}
        return await self.get_list_async(filter_dict)

    async def find_pending_deliveries(self, hours_ago: int = 24) -> List[TerminallogDeliveryStatus]:
        """
        Find pending delivery statuses

        Searches for messages that were published within the specified time frame
        and haven't been completely delivered yet.

        Args:
            hours_ago: How many hours back to search (default: 24 hours)

        Returns:
            List[TerminallogDeliveryStatus]: List of pending delivery status documents
        """
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        filter_dict = {
            "published_at": {"$gte": time_threshold},
            "status": {"$nin": ["delivered"]},
        }
        return await self.get_list_async(filter_dict)

    async def update_service_status(
        self, event_id: str, service_name: str, status: str, received_at: datetime = None, message: str = None
    ) -> bool:
        """
        Update the status of a specific service

        Updates the receipt status of a specific service for a given event.

        Args:
            event_id: Target event ID
            service_name: Target service name
            status: New status (pending/received/failed)
            received_at: Receipt timestamp (current time if None)
            message: Additional message

        Returns:
            bool: True if update was successful, False otherwise
        """
        if received_at is None:
            received_at = get_app_time()

        # Update service status
        update_dict = {
            "$set": {
                "services.$[elem].status": status,
                "services.$[elem].received_at": received_at,
                "last_updated_at": get_app_time(),
            }
        }

        if message is not None:
            update_dict["$set"]["services.$[elem].message"] = message

        array_filters = [{"elem.service_name": service_name}]

        if self.dbcollection is None:
            await self.initialize()

        try:
            result = await self.dbcollection.update_one(
                {"event_id": event_id}, update_dict, array_filters=array_filters, session=self.session
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update service status: {e}")
            return False

    async def update_delivery_status(self, event_id: str, status: str) -> bool:
        """
        Update overall delivery status

        Args:
            event_id: Target event ID
            status: New status (published/delivered/partially_delivered/failed)

        Returns:
            bool: True if update was successful, False otherwise
        """
        update_dict = {"status": status, "last_updated_at": get_app_time()}
        return await self.update_one_async({"event_id": event_id}, update_dict)

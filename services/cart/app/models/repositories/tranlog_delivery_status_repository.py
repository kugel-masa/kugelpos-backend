# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
TranlogDeliveryStatus repository module

This module provides repository classes for managing transaction log delivery statuses.
It handles storing, retrieving, and updating the delivery status of transaction logs.
"""
from logging import getLogger
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from datetime import datetime, timedelta

from kugel_common.utils.misc import get_app_time
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from app.models.documents.tranlog_delivery_status_document import TranlogDeliveryStatus
from app.config.settings import settings

logger = getLogger(__name__)


class TranlogDeliveryStatusRepository(AbstractRepository[TranlogDeliveryStatus]):
    """
    Transaction Log Delivery Status Repository

    A repository for managing transaction log delivery statuses,
    extending AbstractRepository and providing specific implementation
    for MongoDB operations related to transaction log delivery tracking.
    """

    def __init__(self, db: AsyncIOMotorDatabase, terminal_info: TerminalInfoDocument):
        """
        Initialize the repository

        Args:
            db: MongoDB database connection instance
        """
        super().__init__(settings.DB_COLLECTION_NAME_TRAN_LOG_DELIVERY_STATUS, TranlogDeliveryStatus, db)
        self.terminal_info = terminal_info

    async def create_status_async(
        self, event_id: str, transaction_no: int, payload: dict, services: List[dict] = None
    ) -> bool:
        """
        Create a new delivery status document

        Args:
            event_id: Event ID (UUID)
            transaction_no: Transaction number
            payload: Message payload
            services: List of service dictionaries

        Returns:
            bool: True if creation was successful, False otherwise

        Raises:
            DuplicateKeyException: If a document with the same key already exists
            RepositoryException: If any other database error occurs
        """
        now = get_app_time()
        tenant_id = self.terminal_info.tenant_id
        store_code = self.terminal_info.store_code
        terminal_no = self.terminal_info.terminal_no
        business_date = self.terminal_info.business_date
        open_counter = self.terminal_info.open_counter

        # Process service information
        service_status_list = []
        if services:
            for service in services:
                service_status = TranlogDeliveryStatus.ServiceStatus(
                    service_name=service.get("service_name"), status=service.get("status", "pending")
                )
                service_status_list.append(service_status)

        # Create document
        tranlog_delivery_status = TranlogDeliveryStatus(
            event_id=event_id,
            published_at=now,
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=terminal_no,
            transaction_no=transaction_no,
            business_date=business_date,
            open_counter=open_counter,
            payload=payload,
            services=service_status_list,
            status="published",
            last_updated_at=now,
        )

        # Save to database
        return await self.create_async(tranlog_delivery_status)

    async def find_by_event_id(self, event_id: str) -> Optional[TranlogDeliveryStatus]:
        """
        Find delivery status by event ID

        Args:
            event_id: Event ID to search for

        Returns:
            TranlogDeliveryStatus: Matching document if found, None otherwise
        """
        return await self.get_one_async({"event_id": event_id})

    async def find_by_transaction_info(
        self, tenant_id: str, store_code: str, terminal_no: int, transaction_no: int
    ) -> List[TranlogDeliveryStatus]:
        """
        Find delivery statuses by transaction information

        Args:
            tenant_id: Tenant ID
            store_code: Store code
            terminal_no: Terminal number
            transaction_no: Transaction number

        Returns:
            List[TranlogDeliveryStatus]: List of matching delivery status documents
        """
        filter_dict = {
            "tenant_id": tenant_id,
            "store_code": store_code,
            "terminal_no": terminal_no,
            "transaction_no": transaction_no,
        }
        return await self.get_list_async(filter_dict)

    async def find_by_business_date(
        self, tenant_id: str, store_code: str, business_date: str
    ) -> List[TranlogDeliveryStatus]:
        """
        Find delivery statuses by business date

        Args:
            tenant_id: Tenant ID
            store_code: Store code
            business_date: Business date (YYYYMMDD format)

        Returns:
            List[TranlogDeliveryStatus]: List of matching delivery status documents
        """
        filter_dict = {"tenant_id": tenant_id, "store_code": store_code, "business_date": business_date}
        return await self.get_list_async(filter_dict)

    async def find_pending_deliveries(self, hours_ago: int = 24) -> List[TranlogDeliveryStatus]:
        """
        Find pending delivery statuses

        Searches for messages that were published within the specified time frame
        and haven't been completely delivered yet.

        Args:
            hours_ago: How many hours back to search (default: 24 hours)

        Returns:
            List[TranlogDeliveryStatus]: List of pending delivery status documents
        """
        time_threshold = get_app_time() - timedelta(hours=hours_ago)
        filter_dict = {
            "published_at": {"$gte": time_threshold},
            # not in delivered status
            "status": {"$nin": ["delivered"]},
        }
        return await self.get_list_async(filter_dict)

    async def update_service_status(
        self, event_id: str, service_name: str, status: str, update_time: datetime = None, message: str = None
    ) -> bool:
        """
        Update the status of a specific service

        Updates the status of a specific service for a given event.

        Args:
            event_id: Target event ID
            service_name: Target service name
            status: New status (pending/delivered/failed)
            update_time: Update timestamp (current time if None)
            message: Additional message

        Returns:
            bool: True if update was successful, False otherwise
        """
        if update_time is None:
            update_time = get_app_time()

        # Update service status
        update_dict = {
            "$set": {
                "services.$[elem].status": status,
                "services.$[elem].update_time": update_time,
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

            # Check all service statuses to update overall status
            if result.modified_count > 0:
                doc = await self.find_by_event_id(event_id)
                if doc:
                    all_delivered = all(service.status == "delivered" for service in doc.services)
                    any_failed = any(service.status == "failed" for service in doc.services)
                    any_pending = any(service.status == "pending" for service in doc.services)

                    if any_failed:
                        await self.update_delivery_status(event_id, "partially_delivered")
                    elif all_delivered:
                        await self.update_delivery_status(event_id, "delivered")
                    elif any_pending:
                        await self.update_delivery_status(event_id, "published")

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
        return await self.update_one_async({"event_id": event_id}, update_dict, max_retries=10)

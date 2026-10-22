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
            # Not handed to the broker yet (issue #230). This document is created in
            # the transaction that stores the log, and the publish comes after the
            # commit. Written as "published", a log never published because the
            # process stopped in between would not be republished.
            status="pending",
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

    async def mark_warning_sent(self, event_id: str) -> bool:
        """
        Record that the undelivered warning for this log has been sent (issue #230)

        Without the record the warning went out on every republish run, up to 285
        times per log over the 24-hour window.

        Args:
            event_id: Target event ID

        Returns:
            bool: True if update was successful, False otherwise
        """
        return await self.update_one_async({"event_id": event_id}, {"warning_sent_at": get_app_time()})

    async def mark_handed_off(self, event_id: str) -> bool:
        """
        Record that the broker has taken this log (issue #230)

        Sets the overall status to ``published`` and stamps ``handed_off_at``. The
        stamp is written here and nowhere else, so it only ever means a hand-off.

        Args:
            event_id: Target event ID

        Returns:
            bool: True if update was successful, False otherwise
        """
        now = get_app_time()
        return await self.update_one_async(
            {"event_id": event_id}, {"status": "published", "handed_off_at": now, "last_updated_at": now}
        )

    async def find_latest_received_published_at(
        self, service_name: str, since: datetime, received_before: datetime
    ) -> Optional[datetime]:
        """
        The newest ``published_at`` among the logs ``service_name`` has acknowledged (issue #230)

        It stands for how far the consumer has read. A log handed to the broker
        before this point and still unacknowledged by the consumer was most likely
        skipped: the queue is read in order. The order is not strict (concurrent
        handlers, Dapr retries), but the 15-minute wait and the one-run margin make
        that rare, and a copy that arrives while the original is still being
        processed is dropped by event_id. Both topics (cash in/out and open/close)
        count: one sidecar declares both subscriptions when it starts, and the open
        log, the first publish after a start, would otherwise wait for the close log.

        ``published_at`` is when the document was created, never later than the
        hand-off, so the point is never overestimated. Acknowledgements newer than
        ``received_before`` are left out: a log handed off just before them may still
        be in the consumer's hands.

        Args:
            service_name: Consumer to look at
            since: Start of the republish window
            received_before: Only acknowledgements at or before this time count

        Returns:
            Optional[datetime]: The newest ``published_at`` (UTC), or None if the
            consumer has acknowledged nothing in the window
        """
        if self.dbcollection is None:
            await self.initialize()
        doc = await self.dbcollection.find_one(
            {
                "published_at": {"$gte": since},
                "services": {
                    "$elemMatch": {
                        "service_name": service_name,
                        "status": "received",
                        "received_at": {"$lte": received_before},
                    }
                },
            },
            projection={"published_at": 1},
            sort=[("published_at", -1)],
            session=self.session,
        )
        if doc is None:
            return None
        published_at: datetime = doc["published_at"]
        # MongoDB returns naive UTC.
        return published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)

    async def claim_republish(self, event_id: str, until: datetime) -> bool:
        """
        Take on the one-time republish of a skipped log (issue #230)

        The job can run in more than one worker, so only the worker whose conditional
        update matches sends it. A claim whose worker stopped before sending expires
        at ``until``, and the next run takes it over.

        Args:
            event_id: Target event ID
            until: When the claim expires

        Returns:
            bool: True if this caller holds the claim
        """
        if self.dbcollection is None:
            await self.initialize()
        result = await self.dbcollection.update_one(
            {
                "event_id": event_id,
                "republished_at": None,
                "$or": [
                    {"republish_claim_expires_at": None},
                    {"republish_claim_expires_at": {"$lte": get_app_time()}},
                ],
            },
            {"$set": {"republish_claim_expires_at": until}},
            session=self.session,
        )
        return result.modified_count == 1

    async def mark_republished(self, event_id: str) -> bool:
        """
        Record that the skipped log has been sent again (issue #230). It is not sent a third time.

        Args:
            event_id: Target event ID

        Returns:
            bool: True if update was successful, False otherwise
        """
        return await self.update_one_async({"event_id": event_id}, {"republished_at": get_app_time()})

    async def update_delivery_status(self, event_id: str, status: str) -> bool:
        """
        Update overall delivery status

        Args:
            event_id: Target event ID
            status: New status (pending/publish_failed/published/delivered/partially_delivered/failed)

        Returns:
            bool: True if update was successful, False otherwise
        """
        update_dict = {"status": status, "last_updated_at": get_app_time()}
        return await self.update_one_async({"event_id": event_id}, update_dict)

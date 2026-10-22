# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Dict, Any, List
from pydantic import ConfigDict
from datetime import datetime

from kugel_common.models.documents.abstract_document import AbstractDocument

#: Overall statuses of a terminal log the broker has not taken yet (issue #230).
#: Only these are republished on every run. ``pending`` covers the gap between the
#: commit that creates the document and the publish after it; ``publish_failed`` is
#: a publish the broker refused. Once the broker has taken a log, a durable queue
#: holds it, so sending it again on every run only adds copies. The exception is a
#: log a consumer has read past without acknowledging it, which is sent once more.
NOT_HANDED_TO_BROKER_STATUSES = ("pending", "publish_failed")


class TerminallogDeliveryStatus(AbstractDocument):
    """
    Document model for managing terminal log delivery status

    This model is used to track and manage the delivery status of terminal log messages
    published through pubsub. It also records receipt confirmations from each service.
    """

    class ServiceStatus(AbstractDocument):
        """
        Internal class representing the reception status of each service
        """

        service_name: str  # Service name
        received_at: Optional[datetime] = None  # Received datetime
        status: str = "pending"  # Status (pending/received/failed)
        message: Optional[str] = None  # Error message etc.

    # Message key information
    event_id: str  # Event ID (UUID)
    published_at: datetime  # Published datetime
    # Overall status (pending/publish_failed/published/delivered/partially_delivered/failed).
    # "failed" means every service reported failure, or the log cannot be republished.
    status: str = "published"

    # Terminal-related information
    tenant_id: str  # Tenant ID
    store_code: str  # Store code
    terminal_no: int  # Terminal number
    business_date: str  # Business date (YYYYMMDD)
    open_counter: int  # Opening count

    # Message body and reception status of each service
    payload: Dict[str, Any]  # Message body
    services: List[ServiceStatus] = []  # Reception status of each service

    # Update information
    last_updated_at: datetime  # Last updated datetime

    # When the undelivered warning was sent. It is sent once per log (issue #230).
    warning_sent_at: Optional[datetime] = None

    # When the broker took the log. ``published_at`` is when the document was
    # created, earlier than the hand-off for a log the broker first refused.
    handed_off_at: Optional[datetime] = None
    # A log a consumer has read past is sent once more (issue #230): when the claim
    # of the worker sending it expires, and when it was sent.
    republish_claim_expires_at: Optional[datetime] = None
    republished_at: Optional[datetime] = None

# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, Dict, Any, List
from pydantic import ConfigDict
from datetime import datetime

from kugel_common.models.documents.abstract_document import AbstractDocument


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
    status: str = "published"  # Overall status (published/delivered/partially_delivered/failed)

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

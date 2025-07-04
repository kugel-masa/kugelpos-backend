# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Terminal API Schemas Module

This module defines the Pydantic schema classes used for API request and response
data validation and serialization in the Terminal service. These classes extend
base schemas defined in the common schemas module.

Each class represents a specific data structure used in the API endpoints for:
- Terminals management
- Store management
- Tenant management
- Staff management
- Cash operations
"""

from app.api.common.schemas import *


# Store-related schemas
class StoreCreateRequest(BaseStoreCreateRequest):
    """Schema for store creation request"""

    pass


class StoreDeleteResponse(BaseStoreDeleteResponse):
    """Schema for store deletion response"""

    pass


class Store(BaseStore):
    """Schema for store information"""

    pass


class StoreUpdateRequest(BaseStoreUpdateRequest):
    """Schema for store update request"""

    pass


# Tenant-related schemas
class Tenant(BaseTenant):
    """Schema for tenant information"""

    pass


class TenantCreateRequest(BaseTenantCreateReqest):
    """Schema for tenant creation request"""

    pass


class TenantUpdateRequest(BaseTenantUpdateRequest):
    """Schema for tenant update request"""

    pass


class TenantDeleteResponse(BaseTenantDeleteResponse):
    """Schema for tenant deletion response"""

    pass


# Terminal-related schemas
class Terminal(BaseTerminal):
    """
    Schema for terminal information

    This schema represents a terminal device in the POS system, including
    its identification, status, and operational information.
    """

    pass


class TerminalCreateRequest(BaseTerminalCreateRequest):
    """
    Schema for terminal creation request

    Contains the required information to create a new terminal:
    - store_code: The store code where the terminal is located
    - terminal_no: The terminal number unique within the store
    - description: Optional description of the terminal
    """

    pass


class TerminalUpdateRequest(BaseTerminalUpdateRequest):
    """
    Schema for terminal update request

    Contains fields that can be updated for a terminal:
    - description: The new description for the terminal
    """

    pass


class TerminalOpenRequest(BaseTerminalOpenRequest):
    """
    Schema for terminal open request

    Contains information required to open a terminal:
    - initial_amount: The initial cash amount in the terminal drawer
    """

    pass


class TerminalCloseRequest(BaseTerminalCloseRequest):
    """
    Schema for terminal close request

    Contains information required to close a terminal:
    - physical_amount: The counted physical cash amount in the terminal drawer
    """

    pass


class TerminalSignInRequest(BaseTerminalSignInRequest):
    """
    Schema for terminal sign-in request

    Contains information required to sign into a terminal:
    - staff_id: The ID of the staff member signing into the terminal
    """

    pass


class TerminalDeleteResponse(BaseTerminalDeleteResponse):
    """
    Schema for terminal deletion response

    Contains information returned after deleting a terminal:
    - terminal_id: The ID of the deleted terminal
    """

    pass


# Staff-related schemas
class Staff(BaseStaff):
    """Schema for staff information"""

    pass


# Function mode-related schemas
class UpdateFunctionModeRequest(BaseUpdateFunctionModeRequest):
    """
    Schema for terminal function mode update request

    Contains information required to update a terminal's function mode:
    - function_mode: The new function mode for the terminal
      (e.g., MainMenu, Sales, Return, etc.)
    """

    pass


# Cash operation-related schemas
class CashInOutRequest(BaseCashInOutRequest):
    """
    Schema for cash in/out request

    Contains information required for cash drawer operations:
    - amount: The amount to add (positive) or remove (negative)
    - description: Optional description for the transaction
    """

    pass


class CashInOutResponse(BaseCashInOutResponse):
    """
    Schema for cash in/out response

    Contains information returned after cash drawer operations:
    - terminal_id: The ID of the terminal where the operation occurred
    - amount: The amount added or removed
    - description: Description of the transaction
    - receipt_text: Formatted text for receipt printing
    - journal_text: Formatted text for journal entry
    """

    pass


class TerminalOpenResponse(BaseTerminalOpenResponse):
    """
    Schema for terminal open response

    Contains information returned after opening a terminal:
    - terminal_id: The ID of the opened terminal
    - business_date: The business date assigned to the terminal
    - open_counter: The terminal open counter (incremented on each open)
    - receipt_text: Formatted text for receipt printing
    - journal_text: Formatted text for journal entry
    """

    pass


class TerminalCloseResponse(BaseTerminalCloseResponse):
    """
    Schema for terminal close response

    Contains information returned after closing a terminal:
    - terminal_id: The ID of the closed terminal
    - business_date: The business date for the closed session
    - open_counter: The terminal open counter for the closed session
    - business_counter: The business counter (incremented on each close)
    - receipt_text: Formatted text for receipt printing
    - journal_text: Formatted text for journal entry
    """

    pass


class DeliveryStatusUpdateRequest(BaseModel):
    """
    API model for delivery status update requests.
    Contains parameters needed to update the delivery status of a transaction.
    """

    event_id: str
    service: str
    status: str
    message: Optional[str] = None


class DeliveryStatusUpdateResponse(BaseModel):
    """
    API model for delivery status update responses.
    Returns the result of updating the delivery status.
    """

    event_id: str
    service: str
    status: str
    success: bool

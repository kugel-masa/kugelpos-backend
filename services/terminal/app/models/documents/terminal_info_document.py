# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.utils.misc import to_lower_camel
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument


class TerminalInfoDocument(AbstractDocument):
    """
    Terminal Information Document

    This class represents a terminal in the POS system and contains all information
    related to a physical terminal device, including its status, configuration, and
    current operating state.

    Terminals belong to a specific tenant and store, and are identified by a tenant_id,
    store_code, and terminal_no combination.
    """

    tenant_id: str = None  # Tenant ID that owns this terminal
    store_code: str = None  # Store code where this terminal is located
    terminal_no: int = None  # Terminal number within the store
    description: Optional[str] = None  # Description of the terminal
    terminal_id: Optional[str] = None  # Unique terminal ID (format: tenant_id-store_code-terminal_no)
    function_mode: Optional[str] = None  # Current function mode of the terminal (e.g., Sales, Returns, etc.)
    status: Optional[str] = None  # Current status of the terminal (e.g., Opened, Closed, etc.)
    business_date: Optional[str] = None  # Current business date (YYYYMMDD)
    open_counter: Optional[int] = None  # Counter incremented each time the terminal is opened
    business_counter: Optional[int] = None  # Counter incremented for each business operation
    staff: Optional[StaffMasterDocument] = None  # Staff member currently signed in to the terminal
    initial_amount: Optional[float] = None  # Initial cash amount when the terminal was opened
    physical_amount: Optional[float] = None  # Physical cash amount counted at terminal close
    api_key: Optional[str] = None  # API key for terminal authentication
    tags: Optional[list[str]] = None  # Additional tags for categorization

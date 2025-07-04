# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from pydantic import ConfigDict

from kugel_common.utils.misc import to_lower_camel
from app.models.documents.abstract_document import AbstractDocument
from app.models.documents.staff_master_document import StaffMasterDocument


class TerminalInfoDocument(AbstractDocument):
    """
    Document class representing POS terminal information in the master data system.

    This class defines the attributes of a terminal (POS device) in the system,
    including its location, status, current business day, assigned staff member,
    and cash handling information. It serves as a record of terminal state
    and configuration.
    """

    tenant_id: str = None  # Unique identifier for the tenant (multi-tenancy support)
    store_code: str = None  # Code identifying the store where this terminal is located
    terminal_no: int = None  # Numeric identifier for the terminal within the store
    description: Optional[str] = None  # Human-readable description of the terminal
    terminal_id: Optional[str] = None  # System identifier for the terminal
    status: Optional[str] = None  # Current operational status of the terminal
    business_date: Optional[str] = None  # Current business date for this terminal
    business_counter: Optional[int] = None  # Counter that increments with each business day
    staff: Optional[StaffMasterDocument] = None  # Currently logged-in staff member
    initial_amount: Optional[float] = None  # Initial cash amount in the register
    api_key: Optional[str] = None  # API key for terminal authentication

    # Configure Pydantic to use camelCase for JSON serialization
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

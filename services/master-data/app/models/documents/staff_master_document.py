# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from app.models.documents.abstract_document import AbstractDocument


class StaffMasterDocument(AbstractDocument):
    """
    Document class representing staff member information in the master data system.

    This class defines the attributes of staff members (employees) who interact
    with the POS system, including their identification, authentication credentials,
    and assigned roles that determine their access permissions.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    id: Optional[str] = None  # Unique identifier for the staff member
    name: Optional[str] = None  # Display name of the staff member
    pin: Optional[str] = None  # Personal identification number for authentication
    status: Optional[str] = None  # Current status of the staff member (e.g., active, inactive)
    roles: Optional[list] = []  # List of roles assigned to this staff member that determine permissions

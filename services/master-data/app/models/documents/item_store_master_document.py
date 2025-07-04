# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from datetime import datetime
from enum import Enum
from app.models.documents.abstract_document import AbstractDocument


class ItemStoreMasterDocument(AbstractDocument):
    """
    Document class representing store-specific item information in the master data system.

    This class defines store-specific overrides for items, such as custom pricing
    at individual store locations. It allows for location-specific pricing strategies
    while maintaining common item information centrally.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    store_code: Optional[str] = None  # Identifier for the specific store
    item_code: Optional[str] = None  # Reference to the common item this store-specific record relates to
    store_price: Optional[float] = None  # Store-specific price that overrides the standard price

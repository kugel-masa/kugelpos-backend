# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from datetime import datetime
from pydantic import ConfigDict

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel


class ItemMasterDocument(AbstractDocument):
    """
    Document model representing item master data.

    This class defines the structure for storing product information including
    pricing, descriptions, categorization, and other attributes.
    """

    tenant_id: Optional[str] = None  # Identifier for the tenant
    store_code: Optional[str] = None  # Code identifying the store
    item_code: Optional[str] = None  # Unique identifier for the item
    description: Optional[str] = None  # Standard item description
    description_short: Optional[str] = None  # Short version of the description
    description_long: Optional[str] = None  # Detailed description
    manufacturer_code: Optional[str] = None  # Manufacturer's product code
    unit_price: Optional[float] = 0.0  # Standard unit price
    unit_cost: Optional[float] = 0.0  # Cost of the item
    item_details: Optional[list[str]] = None  # Additional details as a list of strings
    image_urls: Optional[list[str]] = None  # URLs to product images
    category_code: Optional[str] = None  # Product category code
    tax_code: Optional[str] = None  # Tax category code
    is_discount_restricted: Optional[bool] = False  # Flag indicating if discounts can be applied
    is_deleted: Optional[bool] = False  # Soft delete flag
    store_price: Optional[float] = 0.0  # Store-specific price (may differ from unit price)
    entry_date: Optional[datetime] = None  # Date when the item was first created
    last_update_date: Optional[datetime] = None  # Date of the last update to the item

    # Configuration for Pydantic model to use camelCase field names in JSON
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

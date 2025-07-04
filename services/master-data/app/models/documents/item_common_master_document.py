# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from app.models.documents.abstract_document import AbstractDocument


class ItemCommonMasterDocument(AbstractDocument):
    """
    Document class representing common item/product information in the master data system.

    This class defines the core attributes of a product that are shared across all stores
    within a tenant. It includes basic identification, descriptive information, standard
    pricing, categorization, and tax classification.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    item_code: Optional[str] = None  # Unique code identifying this item within a tenant
    category_code: Optional[str] = None  # Reference to the category this item belongs to
    description: Optional[str] = None  # Standard description of the item
    description_short: Optional[str] = None  # Abbreviated description for display purposes
    description_long: Optional[str] = None  # Extended description with more detailed information
    unit_price: Optional[float] = 0.0  # Standard selling price per unit
    unit_cost: Optional[float] = 0.0  # Cost price per unit
    item_details: Optional[list[str]] = None  # Additional details or specifications about the item
    image_urls: Optional[list[str]] = None  # List of URLs to images of the item
    tax_code: Optional[str] = None  # Reference to the tax code applied to this item
    is_discount_restricted: Optional[bool] = False  # Flag indicating if discounts can be applied to this item
    is_deleted: Optional[bool] = False  # Logical deletion flag

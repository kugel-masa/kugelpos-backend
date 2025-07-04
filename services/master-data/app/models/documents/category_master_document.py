# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from app.models.documents.abstract_document import AbstractDocument


class CategoryMasterDocument(AbstractDocument):
    """
    Document class representing a product/item category in the master data system.

    This class defines the structure for category information which is used to classify
    and group items. Categories are fundamental for organizing products, applying tax rules,
    and facilitating reporting and analytics.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    category_code: Optional[str] = None  # Unique code identifying this category within a tenant
    description: Optional[str] = None  # Full description of the category
    description_short: Optional[str] = None  # Abbreviated description for display purposes
    tax_code: Optional[str] = None  # Reference to the tax code applied to items in this category

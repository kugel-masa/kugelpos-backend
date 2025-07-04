# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from datetime import datetime

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel


class StoreInfo(BaseDocumentModel):
    """
    Store Information Model

    This class represents a store within a tenant in the POS system.
    It contains basic information about a physical store location.
    """

    store_code: Optional[str] = None  # Unique store code within a tenant
    store_name: Optional[str] = None  # Display name of the store
    status: Optional[str] = None  # Current status of the store (e.g., Active, Inactive)
    business_date: Optional[str] = None  # Current business date for the store (YYYYMMDD)
    tags: Optional[list[str]] = None  # Additional tags for categorization
    created_at: Optional[datetime] = None  # Timestamp when the store record was created
    updated_at: Optional[datetime] = None  # Timestamp when the store record was last updated


class TenantInfoDocument(AbstractDocument):
    """
    Tenant Information Document

    This class represents a tenant in the POS system. A tenant is typically
    a business entity that owns one or more stores. This document contains
    the basic information about a tenant and its stores.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant
    tenant_name: Optional[str] = None  # Display name of the tenant
    stores: Optional[list[StoreInfo]] = None  # List of stores belonging to this tenant
    tags: Optional[list[str]] = None  # Additional tags for categorization

# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
API V1 Request and Response Schema Definitions

This module defines all request and response schemas used in the API v1 of the master-data service.
These schemas inherit from base schema classes (BaseXXX) defined in common/schemas.py and
can be extended as needed.

Each class extends Pydantic's BaseModel and is used for FastAPI request/response validation
and automatic documentation generation.
"""

from app.api.common.schemas import (
    BaseStaffResponse,
    BaseStaffCreateRequest,
    BaseStaffUpdateRequest,
    BaseStaffDeleteResponse,
    BaseItemResponse,
    BaseItemCreateRequest,
    BaseItemUpdateRequest,
    BaseItemDeleteResponse,
    BaseItemStoreResponse,
    BaseItemStoreCreateRequest,
    BaseItemStoreUpdateRequest,
    BaseItemStoreDeleteResponse,
    BaseItemStoreDetailResponse,
    BasePaymentResponse,
    BasePaymentCreateRequest,
    BasePaymentUpdateRequest,
    BasePaymentDeleteResponse,
    BaseSettingsMasterValue,
    BaseSettingsMasterCreateRequest,
    BaseSettingsMasterUpdateRequest,
    BaseSettingsMasterResponse,
    BaseSettingsMasterValueResponse,
    BaseSettingsMasterDeleteResponse,
    BaseTenantCreateRequest,
    BaseTenantCreateResponse,
    BaseCategoryMasterCreateRequest,
    BaseCategoryMasterUpdateRequest,
    BaseCategoryMasterResponse,
    BaseCategoryMasterDeleteResponse,
    BaseItemBookButton,
    BaseItemBookTab,
    BaseItemBookCategory,
    BaseItemBookResponse,
    BaseItemBookCreateRequest,
    BaseItemBookUpdateRequest,
    BaseItemBookDeleteResponse,
    BaseItemBookCategoryDeleteResponse,
    BaseItemBookTabDeleteResponse,
    BaseItemBookButtonDeleteResponse,
    BaseTaxMasterResponse,
)

# Staff related schema definitions


class StaffCreateRequest(BaseStaffCreateRequest):
    """
    Staff Creation Request Schema

    Contains staff ID, name, PIN code, roles and other information
    used to create a new staff record.
    """

    pass


class StaffUpdateRequest(BaseStaffUpdateRequest):
    """
    Staff Update Request Schema

    Used to update an existing staff record.
    Contains name, PIN code, roles and other information.
    """

    pass


class StaffResponse(BaseStaffResponse):
    """
    Staff Response Schema

    Defines the response format for staff data from the API.
    Contains detailed staff information along with creation and last update timestamps.
    """

    pass


class StaffDeleteResponse(BaseStaffDeleteResponse):
    """
    Staff Delete Response Schema

    Used to return the result of a staff deletion operation.
    Contains the ID of the deleted staff.
    """

    pass


# Item related schema definitions


class ItemCreateRequest(BaseItemCreateRequest):
    """
    Item Creation Request Schema

    Contains item code, description, unit price, unit cost, category,
    tax code, and other information used to create a new item record.
    """

    pass


class ItemUpdateRequest(BaseItemUpdateRequest):
    """
    Item Update Request Schema

    Used to update an existing item record.
    Contains description, unit price, unit cost, category, tax code, and other information.
    """

    pass


class ItemResponse(BaseItemResponse):
    """
    Item Response Schema

    Defines the response format for item data from the API.
    Contains detailed item information along with creation and last update timestamps.
    """

    pass


class ItemDeleteResponse(BaseItemDeleteResponse):
    """
    Item Delete Response Schema

    Used to return the result of an item deletion operation.
    Contains the code of the deleted item and a flag indicating logical deletion.
    """

    pass


# Store-specific item related schema definitions


class ItemStoreCreateRequest(BaseItemStoreCreateRequest):
    """
    Store-specific Item Creation Request Schema

    Used to create store-specific item information (mainly price).
    Allows for store-specific price settings for common master items.
    """

    pass


class ItemStoreUpdateRequest(BaseItemStoreUpdateRequest):
    """
    Store-specific Item Update Request Schema

    Used to update existing store-specific item information.
    Primarily updates store-specific prices.
    """

    pass


class ItemStoreResponse(BaseItemStoreResponse):
    """
    Store-specific Item Response Schema

    Defines the response format for store-specific item data from the API.
    Contains item code, store-specific price, and other information.
    """

    pass


class ItemStoreDeleteResponse(BaseItemStoreDeleteResponse):
    """
    Store-specific Item Delete Response Schema

    Used to return the result of a store-specific item information deletion operation.
    Contains the code of the deleted item.
    """

    pass


class ItemStoreDetailResponse(BaseItemStoreDetailResponse):
    """
    Store-specific Item Detail Response Schema

    Defines the response format for detailed information that combines common master
    item information with store-specific item information. Contains complete
    item information intended for POS terminals.
    """

    pass


# Payment method related schema definitions


class PaymentCreateRequest(BasePaymentCreateRequest):
    """
    Payment Method Creation Request Schema

    Contains payment code, description, limit amount, refund capability flags,
    and other information used to create a new payment method record.
    """

    pass


class PaymentUpdateRequest(BasePaymentUpdateRequest):
    """
    Payment Method Update Request Schema

    Used to update an existing payment method record.
    Contains description, limit amount, refund capability flags, and other information.
    """

    pass


class PaymentResponse(BasePaymentResponse):
    """
    Payment Method Response Schema

    Defines the response format for payment method data from the API.
    Contains detailed payment method information along with creation and last update timestamps.
    """

    pass


class PaymentDeleteResponse(BasePaymentDeleteResponse):
    """
    Payment Method Delete Response Schema

    Used to return the result of a payment method deletion operation.
    Contains the code of the deleted payment method.
    """

    pass


# Settings master related schema definitions


class SettingsMasterValue(BaseSettingsMasterValue):
    """
    Settings Value Schema

    Defines setting values associated with specific stores or terminals.
    Contains store code, terminal number, and the setting value.
    """

    pass


class SettingsMasterCreateRequest(BaseSettingsMasterCreateRequest):
    """
    Settings Master Creation Request Schema

    Contains setting name, default value, and an array of store/terminal-specific
    setting values used to create a new settings master record.
    """

    pass


class SettingsMasterUpdateRequest(BaseSettingsMasterUpdateRequest):
    """
    Settings Master Update Request Schema

    Used to update an existing settings master record.
    Contains default value and an array of store/terminal-specific setting values.
    """

    pass


class SettingsMasterResponse(BaseSettingsMasterResponse):
    """
    Settings Master Response Schema

    Defines the response format for settings master data from the API.
    Contains setting name, default value, array of store/terminal-specific setting values,
    and creation and last update timestamps.
    """

    pass


class SettingsMasterValueResponse(BaseSettingsMasterValueResponse):
    """
    Settings Value Response Schema

    Defines the response format for retrieving a specific store/terminal setting value.
    Contains the resolved setting value.
    """

    pass


class SettingsMasterDeleteResponse(BaseSettingsMasterDeleteResponse):
    """
    Settings Master Delete Response Schema

    Used to return the result of a settings master deletion operation.
    Contains the name of the deleted setting.
    """

    pass


# Tenant related schema definitions


class TenantCreateRequest(BaseTenantCreateRequest):
    """
    Tenant Creation Request Schema

    Defines the request format for creating a new tenant.
    Contains the tenant ID.
    """

    pass


class TenantCreateResponse(BaseTenantCreateResponse):
    """
    Tenant Creation Response Schema

    Used to return the result of a tenant creation operation.
    Contains the created tenant ID.
    """

    pass


# Category master related schema definitions


class CategoryMasterCreateRequest(BaseCategoryMasterCreateRequest):
    """
    Category Master Creation Request Schema

    Contains category code, description, short description, tax code,
    and other information used to create a new category record.
    """

    pass


class CategoryMasterUpdateRequest(BaseCategoryMasterUpdateRequest):
    """
    Category Master Update Request Schema

    Used to update an existing category record.
    Contains description, short description, tax code, and other information.
    """

    pass


class CategoryMasterResponse(BaseCategoryMasterResponse):
    """
    Category Master Response Schema

    Defines the response format for category master data from the API.
    Contains detailed category information along with creation and last update timestamps.
    """

    pass


class CategoryMasterDeleteResponse(BaseCategoryMasterDeleteResponse):
    """
    Category Master Delete Response Schema

    Used to return the result of a category master deletion operation.
    Contains the code of the deleted category.
    """

    pass


# Item book related schema definitions


class ItemBookButton(BaseItemBookButton):
    """
    Item Book Button Schema

    Defines the button placement and display attributes within an item book.
    Contains position (X,Y), size, image URL, text color, item code, and more.
    """

    pass


class ItemBookTab(BaseItemBookTab):
    """
    Item Book Tab Schema

    Defines tab information within an item book.
    Contains tab number, title, color, and an array of buttons contained within.
    """

    pass


class ItemBookCategory(BaseItemBookCategory):
    """
    Item Book Category Schema

    Defines category information within an item book.
    Contains category number, title, color, and an array of tabs contained within.
    """

    pass


class ItemBookResponse(BaseItemBookResponse):
    """
    Item Book Response Schema

    Defines the response format for item book data from the API.
    Contains book ID, title, category array, and creation and last update timestamps.
    """

    pass


class ItemBookCreateRequest(BaseItemBookCreateRequest):
    """
    Item Book Creation Request Schema

    Contains title and category array used to create a new item book record.
    """

    pass


class ItemBookUpdateRequest(BaseItemBookUpdateRequest):
    """
    Item Book Update Request Schema

    Used to update an existing item book record.
    Contains title and category array.
    """

    pass


class ItemBookDeleteResponse(BaseItemBookDeleteResponse):
    """
    Item Book Delete Response Schema

    Used to return the result of an item book deletion operation.
    Contains the ID of the deleted book.
    """

    pass


class ItemBookCategoryDeleteResponse(BaseItemBookCategoryDeleteResponse):
    """
    Item Book Category Delete Response Schema

    Used to return the result of removing a category from an item book.
    Contains book ID and category number.
    """

    pass


class ItemBookTabDeleteResponse(BaseItemBookTabDeleteResponse):
    """
    Item Book Tab Delete Response Schema

    Used to return the result of removing a tab from a category in an item book.
    Contains book ID, category number, and tab number.
    """

    pass


class ItemBookButtonDeleteResponse(BaseItemBookButtonDeleteResponse):
    """
    Item Book Button Delete Response Schema

    Used to return the result of removing a button from a tab in an item book.
    Contains book ID, category number, tab number, and button position (X,Y).
    """

    pass


# Tax master related schema definitions


class TaxMasterResponse(BaseTaxMasterResponse):
    """
    Tax Master Response Schema

    Defines the response format for tax master data from the API.
    Contains tax code, tax type, tax name, rate value, rounding digit,
    rounding method, and other information.
    """

    pass

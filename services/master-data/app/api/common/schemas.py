# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Common Schema Definitions

This module defines base schema classes used throughout the master-data service.
These base classes are inherited and extended by API v1 specific schema classes.
They are designed to maintain consistency in schema structure and facilitate
migration between versions.

Each class extends Pydantic's BaseModel and is used for FastAPI request/response
validation and automatic documentation generation.
"""

from typing import Optional, TypeVar
from pydantic import BaseModel, ConfigDict

from kugel_common.utils.misc import to_lower_camel
from app.enums.button_size import ButtonSize

T = TypeVar("T")


#  # Base Schema Model  #
class BaseSchemaModel(BaseModel):
    """
    Base class for all schema classes

    This class extends Pydantic's BaseModel and configures it with
    model_config settings for camel case conversion when serializing to JSON.
    It serves as the foundation for all request/response schemas.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)


#  # for service  #
# Staff
class BaseStaffResponse(BaseSchemaModel):
    """
    Base Staff Response Schema

    Defines all fields required for staff master responses.
    Includes staff ID, name, PIN code, list of roles, creation datetime,
    and last update datetime.
    """

    id: str
    name: str
    pin: str
    roles: Optional[list[str]] = []
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseStaffCreateRequest(BaseSchemaModel):
    """
    Base Staff Creation Request Schema

    Defines fields required for creating a new staff record.
    Includes staff ID, name, PIN code, and list of roles.
    """

    id: str
    name: str
    pin: str
    roles: list[str]


class BaseStaffUpdateRequest(BaseSchemaModel):
    """
    Base Staff Update Request Schema

    Defines fields required for updating an existing staff record.
    Includes name, PIN code, and list of roles. Staff ID is obtained from the URL path.
    """

    name: str
    pin: str
    roles: list[str]


class BaseStaffDeleteResponse(BaseSchemaModel):
    """
    Base Staff Delete Response Schema

    Defines fields for returning the identification of a deleted staff.
    Includes the deleted staff ID.
    """

    staff_id: str


# Item
class BaseItemResponse(BaseSchemaModel):
    """
    Base Item Response Schema

    Defines all fields required for item master responses.
    Includes item code, description, unit price, unit cost, item details,
    image URLs, category code, tax code, discount restriction flag,
    deletion flag, creation datetime, and last update datetime.
    """

    item_code: str
    description: str
    unit_price: float
    unit_cost: float
    item_details: list[str]
    image_urls: list[str]
    category_code: str
    tax_code: str
    is_discount_restricted: bool
    is_deleted: bool
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseItemCreateRequest(BaseSchemaModel):
    """
    Base Item Creation Request Schema

    Defines fields required for creating a new item record.
    Includes item code, description, unit price, unit cost, item details,
    image URLs, category code, tax code, and discount restriction flag.
    """

    item_code: str
    description: str
    unit_price: float
    unit_cost: float
    item_details: list[str]
    image_urls: list[str]
    category_code: str
    tax_code: str
    is_discount_restricted: Optional[bool] = False


class BaseItemUpdateRequest(BaseSchemaModel):
    """
    Base Item Update Request Schema

    Defines fields required for updating an existing item record.
    Includes description, unit price, unit cost, item details,
    image URLs, category code, tax code, and discount restriction flag.
    Item code is obtained from the URL path.
    """

    description: str
    unit_price: float
    unit_cost: float
    item_details: list[str]
    image_urls: list[str]
    category_code: str
    tax_code: str
    is_discount_restricted: Optional[bool] = False


class BaseItemDeleteResponse(BaseSchemaModel):
    """
    Base Item Delete Response Schema

    Defines fields for returning the identification of a deleted item.
    Includes the deleted item code and a flag indicating if it's a logical deletion.
    """

    item_code: str
    is_logical: bool


# Item Store
class BaseItemStoreResponse(BaseSchemaModel):
    """
    Base Store-specific Item Response Schema

    Defines fields required for store-specific item responses.
    Includes item code, store-specific price, creation datetime,
    and last update datetime.
    """

    item_code: str
    store_price: float
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseItemStoreCreateRequest(BaseSchemaModel):
    """
    Base Store-specific Item Creation Request Schema

    Defines fields required for creating store-specific item information.
    Includes item code and store-specific price.
    """

    item_code: str
    store_price: float


class BaseItemStoreUpdateRequest(BaseSchemaModel):
    """
    Base Store-specific Item Update Request Schema

    Defines fields required for updating existing store-specific item information.
    Includes store-specific price. Item code is obtained from the URL path.
    """

    store_price: float


class BaseItemStoreDeleteResponse(BaseSchemaModel):
    """
    Base Store-specific Item Delete Response Schema

    Defines fields for returning the identification of a deleted store-specific item.
    Includes the deleted item code.
    """

    item_code: str


class BaseItemStoreDetailResponse(BaseSchemaModel):
    """
    Base Store-specific Item Detail Response Schema

    Defines fields for responses that combine common master item information
    with store-specific item information. Includes item code, description,
    unit price, unit cost, store-specific price, item details, image URLs,
    category code, tax code, discount restriction flag, deletion flag,
    creation datetime, and last update datetime.
    """

    item_code: str
    description: str
    unit_price: float
    unit_cost: float
    store_price: Optional[float] = None
    item_details: list[str]
    image_urls: list[str]
    category_code: str
    tax_code: str
    is_discount_restricted: bool
    is_deleted: bool
    entry_datetime: str
    last_update_datetime: Optional[str] = None


# Payment
class BasePaymentResponse(BaseSchemaModel):
    """
    Base Payment Method Response Schema

    Defines all fields required for payment method master responses.
    Includes payment code, description, limit amount, refund capability,
    deposit overrun permission, change availability, active flag,
    creation datetime, and last update datetime.
    """

    payment_code: str
    description: str
    limit_amount: float
    can_refund: bool
    can_deposit_over: bool
    can_change: bool
    is_active: bool
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BasePaymentCreateRequest(BaseSchemaModel):
    """
    Base Payment Method Creation Request Schema

    Defines fields required for creating a new payment method record.
    Includes payment code, description, limit amount, refund capability,
    deposit overrun permission, change availability, and active flag.
    """

    payment_code: str
    description: str
    limit_amount: float
    can_refund: bool
    can_deposit_over: bool
    can_change: bool
    is_active: bool


class BasePaymentUpdateRequest(BaseSchemaModel):
    """
    Base Payment Method Update Request Schema

    Defines fields required for updating an existing payment method record.
    Includes description, limit amount, refund capability,
    deposit overrun permission, change availability, and active flag.
    Payment code is obtained from the URL path.
    """

    description: str
    limit_amount: float
    can_refund: bool
    can_deposit_over: bool
    can_change: bool
    is_active: bool


class BasePaymentDeleteResponse(BaseSchemaModel):
    """
    Base Payment Method Delete Response Schema

    Defines fields for returning the identification of a deleted payment method.
    Includes the deleted payment code.
    """

    payment_code: str


# Settings Master
class BaseSettingsMasterValue(BaseSchemaModel):
    """
    Base Settings Value Schema

    Defines fields for setting values associated with specific stores or terminals.
    Includes store code, terminal number, and the setting value.
    Used for hierarchical settings resolution.
    """

    store_code: str = None
    terminal_no: Optional[int] = None
    value: str


class BaseSettingsMasterResponse(BaseSchemaModel):
    """
    Base Settings Master Response Schema

    Defines all fields required for settings master responses.
    Includes setting name, default value, array of store/terminal-specific values,
    creation datetime, and last update datetime.
    """

    name: str
    default_value: str
    values: list[BaseSettingsMasterValue]
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseSettingsMasterCreateRequest(BaseSchemaModel):
    """
    Base Settings Master Creation Request Schema

    Defines fields required for creating a new settings master record.
    Includes setting name, default value, and array of store/terminal-specific values.
    """

    name: str
    default_value: str
    values: list[BaseSettingsMasterValue]


class BaseSettingsMasterUpdateRequest(BaseSchemaModel):
    """
    Base Settings Master Update Request Schema

    Defines fields required for updating an existing settings master record.
    Includes default value and array of store/terminal-specific values.
    Setting name is obtained from the URL path.
    """

    default_value: str
    values: list[BaseSettingsMasterValue]


class BaseSettingsMasterValueResponse(BaseSchemaModel):
    """
    Base Settings Value Response Schema

    Defines fields for responses to setting value retrieval requests.
    Includes the resolved setting value.
    """

    value: str


class BaseSettingsMasterDeleteResponse(BaseSchemaModel):
    """
    Base Settings Master Delete Response Schema

    Defines fields for returning the identification of a deleted settings master.
    Includes the deleted setting name.
    """

    name: str


# Tenant
class BaseTenantCreateRequest(BaseSchemaModel):
    """
    Base Tenant Creation Request Schema

    Defines fields required for creating a new tenant.
    Includes tenant ID.
    """

    tenant_id: str


class BaseTenantCreateResponse(BaseSchemaModel):
    """
    Base Tenant Creation Response Schema

    Defines fields for returning the result of a tenant creation operation.
    Includes the created tenant ID.
    """

    tenant_id: str


# Category Master
class BaseCategoryMasterResponse(BaseSchemaModel):
    """
    Base Category Master Response Schema

    Defines all fields required for category master responses.
    Includes category code, description, short description, tax code,
    creation datetime, and last update datetime.
    """

    category_code: str
    description: str
    description_short: str
    tax_code: str
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseCategoryMasterCreateRequest(BaseSchemaModel):
    """
    Base Category Master Creation Request Schema

    Defines fields required for creating a new category record.
    Includes category code, description, short description, and tax code.
    """

    category_code: str
    description: str
    description_short: str
    tax_code: str


class BaseCategoryMasterUpdateRequest(BaseSchemaModel):
    """
    Base Category Master Update Request Schema

    Defines fields required for updating an existing category record.
    Includes description, short description, and tax code.
    Category code is obtained from the URL path.
    """

    description: str
    description_short: str
    tax_code: str


class BaseCategoryMasterDeleteResponse(BaseSchemaModel):
    """
    Base Category Master Delete Response Schema

    Defines fields for returning the identification of a deleted category master.
    Includes the deleted category code.
    """

    category_code: str


# Item Book
class BaseItemBookButton(BaseSchemaModel):
    """
    Base Item Book Button Schema

    Defines fields for button placement and display attributes within an item book.
    Includes position (X,Y), size, image URL, text color, item code,
    unit price (optional), and description (optional).
    """

    pos_x: int
    pos_y: int
    size: ButtonSize
    image_url: str
    color_text: str
    item_code: str
    unit_price: Optional[float] = None  # for getting with detail
    description: Optional[str] = None  # for getting with detail


class BaseItemBookTab(BaseSchemaModel):
    """
    Base Item Book Tab Schema

    Defines fields for tab information within an item book.
    Includes tab number, title, color, and an array of buttons contained within.
    """

    tab_number: int
    title: str
    color: str
    buttons: Optional[list[BaseItemBookButton]] = []


class BaseItemBookCategory(BaseSchemaModel):
    """
    Base Item Book Category Schema

    Defines fields for category information within an item book.
    Includes category number, title, color, and an array of tabs contained within.
    """

    category_number: int
    title: str
    color: str
    tabs: Optional[list[BaseItemBookTab]] = []


class BaseItemBookCreateRequest(BaseSchemaModel):
    """
    Base Item Book Creation Request Schema

    Defines fields required for creating a new item book record.
    Includes title and category array.
    """

    title: str
    categories: Optional[list[BaseItemBookCategory]] = []


class BaseItemBookUpdateRequest(BaseSchemaModel):
    """
    Base Item Book Update Request Schema

    Defines fields required for updating an existing item book record.
    Includes title and category array. Item book ID is obtained from the URL path.
    """

    title: str
    categories: Optional[list[BaseItemBookCategory]] = []


class BaseItemBookResponse(BaseItemBookCreateRequest):
    """
    Base Item Book Response Schema

    Defines all fields required for item book responses.
    Includes item book ID, title, category array, creation datetime,
    and last update datetime.
    """

    item_book_id: str
    title: str
    categories: Optional[list[BaseItemBookCategory]] = []
    entry_datetime: str
    last_update_datetime: Optional[str] = None


class BaseItemBookDeleteResponse(BaseSchemaModel):
    """
    Base Item Book Delete Response Schema

    Defines fields for returning the identification of a deleted item book.
    Includes the deleted item book ID.
    """

    item_book_id: str


class BaseItemBookCategoryDeleteResponse(BaseItemBookDeleteResponse):
    """
    Base Item Book Category Delete Response Schema

    Defines fields for returning the result of removing a category from an item book.
    Includes item book ID and category number.
    """

    category_number: int


class BaseItemBookTabDeleteResponse(BaseItemBookCategoryDeleteResponse):
    """
    Base Item Book Tab Delete Response Schema

    Defines fields for returning the result of removing a tab from a category in an item book.
    Includes item book ID, category number, and tab number.
    """

    tab_number: int


class BaseItemBookButtonDeleteResponse(BaseItemBookTabDeleteResponse):
    """
    Base Item Book Button Delete Response Schema

    Defines fields for returning the result of removing a button from a tab in an item book.
    Includes item book ID, category number, tab number, and button position (X,Y).
    """

    pos_x: int
    pos_y: int


# Tax Master (from settings)
class BaseTaxMasterResponse(BaseSchemaModel):
    """
    Base Tax Master Response Schema

    Defines all fields required for tax master responses.
    Includes tax code, tax type, tax name, rate value, rounding digit,
    rounding method, creation datetime, and last update datetime.
    """

    tax_code: str
    tax_type: str
    tax_name: str
    rate: float
    round_digit: int
    round_method: Optional[str] = None
    entry_datetime: Optional[str] = None
    last_update_datetime: Optional[str] = None

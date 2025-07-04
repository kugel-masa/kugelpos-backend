# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, TypeVar
from pydantic import BaseModel, ConfigDict
from kugel_common.utils.misc import to_lower_camel
from kugel_common.enums import TransactionType

T = TypeVar("T")

# Base Schema Model


class BaseSchemmaModel(BaseModel):
    """
    Base model for all schema models in the application.
    Provides common configuration for camelCase JSON conversion.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)


# Cart Related Schemas


class BaseItem(BaseSchemmaModel):
    """
    Base model representing an item that can be added to a cart.
    Contains the fundamental properties needed for item operations.
    """

    item_code: str
    quantity: int
    unit_price: Optional[float] = None


class BaseItemQuantityUpdateRequest(BaseSchemmaModel):
    """
    Request model for updating the quantity of an item in the cart.
    """

    quantity: int


class BaseItemUnitPriceUpdateRequest(BaseSchemmaModel):
    """
    Request model for updating the unit price of an item in the cart.
    """

    unit_price: float


class BasePaymentRequest(BaseSchemmaModel):
    """
    Request model for processing payments against a cart.
    """

    payment_code: str
    amount: int
    detail: Optional[str] = None


class BaseDiscount(BaseSchemmaModel):
    """
    Model representing a discount applied to an item or the cart.
    Contains details about the discount type, value and resulting amount.
    """

    discount_type: str
    discount_value: float
    discount_amount: float
    discount_detail: Optional[str] = "no detail"


# Transaction Related Schemas


class BaseTranLineItem(BaseSchemmaModel):
    """
    Model representing a line item in a transaction.
    Includes all details about the item including pricing, quantity, discounts and status.
    """

    line_no: int
    item_code: str
    item_name: str
    unit_price: float
    unit_price_original: Optional[float] = None
    is_unit_price_changed: bool
    quantity: int
    amount: float
    discounts: list[BaseDiscount]
    image_urls: list[str]
    is_cancelled: bool


class BaseTranPayment(BaseSchemmaModel):
    """
    Model representing a payment made in a transaction.
    Includes payment method details and amount information.
    """

    payment_no: int
    payment_code: str
    payment_name: str
    payment_amount: float
    payment_detail: Optional[str] = "no detail"


class BaseTranTax(BaseSchemmaModel):
    """
    Model representing tax information for a transaction.
    Contains details about tax type, rate, and applicable amounts.
    """

    tax_no: int
    tax_code: str
    tax_type: str
    tax_name: str
    tax_amount: float
    target_amount: float
    target_quantity: int


class BaseTranStaff(BaseSchemmaModel):
    """
    Model representing staff information associated with a transaction.
    """

    id: str
    name: str


class BaseTranStatus(BaseSchemmaModel):
    """
    Model representing the status of a transaction.
    Contains flags for cancellation, voiding, and refunding.
    """

    is_cancelled: bool = False
    is_voided: bool = False
    is_refunded: bool = False


class BaseTran(BaseSchemmaModel):
    """
    Model representing a transaction record.
    Contains comprehensive transaction data including line items,
    payments, taxes, and related business information.
    """

    tenant_id: str
    store_code: str
    store_name: Optional[str] = None
    terminal_no: int
    total_amount: float
    total_amount_with_tax: float
    total_quantity: int
    total_discount_amount: float
    deposit_amount: float
    change_amount: float
    stamp_duty_amount: Optional[float] = None
    receipt_no: int
    transaction_no: int
    transaction_type: int
    business_date: Optional[str] = None
    generate_date_time: Optional[str] = None
    line_items: Optional[list[BaseTranLineItem]] = None
    payments: Optional[list[BaseTranPayment]] = None
    taxes: Optional[list[BaseTranTax]] = None
    subtotal_discounts: Optional[list[BaseDiscount]] = None
    receipt_text: Optional[str] = None
    journal_text: Optional[str] = None
    staff: Optional[BaseTranStaff] = None
    status: Optional[BaseTranStatus] = None


class BaseCart(BaseTran):
    """
    Model representing a cart in the system, extending the base transaction.
    Includes cart-specific attributes like cart ID, status, and balance information.
    """

    cart_id: str
    cart_status: str
    subtotal_amount: float
    balance_amount: float


# Store and User Related Schemas


class BaseStore(BaseSchemmaModel):
    """
    Model representing store information.
    """

    store_code: str
    store_name: str
    terminal_no: int


class BaseUser(BaseSchemmaModel):
    """
    Model representing user information for cart operations.
    """

    user_id: str
    user_name: str


# Request/Response Models


class BaseCartCreateRequest(BaseSchemmaModel):
    """
    Request model for creating a new cart.
    """

    transaction_type: Optional[int] = TransactionType.NormalSales.value
    user_id: Optional[str] = None
    user_name: Optional[str] = None


class BaseCartCreateResponse(BaseSchemmaModel):
    """
    Response model returned after cart creation.
    """

    cart_id: str


class BaseCartDeleteResponse(BaseSchemmaModel):
    """
    Response model returned after cart deletion.
    """

    message: str


class BaseTenantCreateRequest(BaseSchemmaModel):
    """
    Request model for creating a new tenant.
    """

    tenant_id: str


class BaseTenantCreateResponse(BaseSchemmaModel):
    """
    Response model returned after tenant creation.
    """

    tenant_id: str


class BaseDiscountRequest(BaseSchemmaModel):
    """
    Request model for applying a discount.
    """

    discount_type: str
    discount_value: float
    discount_detail: Optional[str] = None

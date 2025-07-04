# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from pydantic import BaseModel, ConfigDict
from typing import Optional, Generic, TypeVar

from kugel_common.utils.misc import to_lower_camel


# Base Schema Model with camelCase JSON field conversion
class BaseSchemaModel(BaseModel):
    """
    Base schema model that all other schema models should inherit from.
    Converts snake_case Python fields to camelCase JSON fields for API consistency.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)


# Generic type for use in generic models
T = TypeVar("T")


# Transaction response schema
class BaseTranResponse(BaseSchemaModel):
    """
    Base schema for transaction response data.

    Contains the core identifiers for a transaction that has been processed.
    """

    tenant_id: str  # Tenant identifier
    store_code: str  # Store identifier
    terminal_no: int  # Terminal number
    transaction_no: int  # Unique transaction number


# Report template schemas for different aspects of sales reports
class SalesReportTemplate(BaseSchemaModel):
    """
    Template for sales amount, quantity, and count reporting.

    Used for various sales metrics like gross sales, net sales, discounts, etc.
    """

    amount: float  # Total monetary amount
    quantity: int  # Total quantity of items
    count: int  # Count of transactions or line items


class TaxReportTemplate(BaseSchemaModel):
    """
    Template for tax reporting.

    Contains details about a specific tax category and amounts.
    """

    tax_name: str  # Name of the tax (e.g., "Sales Tax", "VAT")
    tax_amount: float  # Total tax amount collected
    target_amount: float  # Amount of sales to which tax was applied
    target_quantity: int  # Quantity of items to which tax was applied


class PaymentReportTemplate(BaseSchemaModel):
    """
    Template for payment method reporting.

    Aggregates payments by payment method.
    """

    payment_name: str  # Name of payment method (e.g., "Cash", "Credit Card")
    amount: float  # Total amount paid using this method
    count: int  # Number of transactions using this method


class CashInOutReportTemplate(BaseSchemaModel):
    """
    Template for cash in/out reporting.

    Tracks cash movements in the drawer not related to sales.
    """

    amount: float  # Total amount of cash added or removed
    count: int  # Number of cash in/out operations


class CashBalanceReportTemplate(BaseSchemaModel):
    """
    Template for cash balance reporting.

    Tracks the expected and actual cash in drawer, plus movements.
    """

    logical_amount: float  # Expected cash amount based on transactions
    physical_amount: Optional[float] = None  # Actual counted cash amount (if available)
    difference_amount: Optional[float] = None  # Difference between logical and physical amounts
    cash_in: CashInOutReportTemplate = None  # Cash added to drawer (float, paid-in)
    cash_out: CashInOutReportTemplate = None  # Cash removed from drawer (payouts, loans)


class BaseSalesReportResponse(BaseSchemaModel):
    """
    Base schema for comprehensive sales report responses.

    Contains all sales metrics, taxes, payments, and cash balances for a
    specific reporting period (terminal session or business day).
    """

    tenant_id: str  # Tenant identifier
    store_code: str  # Store identifier
    terminal_no: Optional[int] = None  # Terminal number (if report is for specific terminal)
    business_date: str  # Business date in YYYYMMDD format
    open_counter: Optional[int] = None  # Open counter (if report is for specific session)
    business_counter: Optional[int] = None  # Business counter
    sales_gross: SalesReportTemplate  # Gross sales before discounts
    sales_net: SalesReportTemplate  # Net sales after all discounts
    discount_for_lineitems: SalesReportTemplate  # Discounts applied to individual items
    discount_for_subtotal: SalesReportTemplate  # Discounts applied to subtotal
    returns: SalesReportTemplate  # Returned items
    taxes: list[TaxReportTemplate]  # List of tax details by category
    payments: list[PaymentReportTemplate]  # List of payments by method
    cash: CashBalanceReportTemplate  # Cash balance and movements
    receipt_text: Optional[str] = None  # Formatted receipt text (if available)
    journal_text: Optional[str] = None  # Formatted journal text (if available)


# Tenant management schemas
class BaseTenantCreateRequest(BaseSchemaModel):
    """
    Base schema for tenant creation request.

    Used to initialize a new tenant in the report service.
    """

    tenant_id: str  # Tenant identifier to create


class BaseTenantCreateResponse(BaseSchemaModel):
    """
    Base schema for tenant creation response.

    Confirms the tenant was successfully created.
    """

    tenant_id: str  # Created tenant identifier

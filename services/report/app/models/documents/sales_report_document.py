# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.documents.staff_master_document import StaffMasterDocument


class SalesReportTemplate(BaseDocumentModel):
    """
    Template class for sales information in a report.

    This class represents sales data including monetary amount,
    item quantity, and transaction count.
    """

    amount: float  # Total monetary amount
    quantity: int  # Total number of items
    count: int  # Total number of transactions


class TaxReportTemplate(BaseDocumentModel):
    """
    Template class for tax information in a report.

    This class represents tax data including tax name, amount,
    and the taxable amount and quantity.
    """

    tax_name: str  # Name of the tax type
    tax_amount: float  # Total tax amount
    target_amount: float  # Amount subject to this tax
    target_quantity: int  # Quantity of items subject to this tax
    tax_type: Optional[str] = None  # Type of tax (External, Internal, Exempt)


class PaymentReportTemplate(BaseDocumentModel):
    """
    Template class for payment information in a report.

    This class represents payment method data including method name,
    total amount, and transaction count.
    """

    payment_name: str  # Name of the payment method
    amount: float  # Total amount paid with this method
    count: int  # Number of transactions using this method


class CashInOutReportTemplate(BaseDocumentModel):
    """
    Template class for cash in/out information in a report.

    This class represents cash operations data including
    the total amount and count of operations.
    """

    amount: float  # Total amount of cash in or out
    count: int  # Number of cash operations


class CashReportTemplate(BaseDocumentModel):
    """
    Template class for cash drawer information in a report.

    This class represents the cash drawer balance including
    logical (expected) amount, physical (actual) amount,
    the difference between them, and cash in/out operations.
    """

    logical_amount: float  # Expected amount in cash drawer
    physical_amount: float  # Actual counted amount in cash drawer
    difference_amount: float  # Difference between logical and physical amounts
    cash_in: CashInOutReportTemplate  # Cash in operations
    cash_out: CashInOutReportTemplate  # Cash out operations


class SalesReportDocument(AbstractDocument):
    """
    Document class representing a sales report.

    This is the main document class for sales reports, containing
    all information related to sales, taxes, payments, and cash operations
    for a specific business day, terminal, and store.
    """

    tenant_id: str  # Identifier for the tenant
    store_code: str  # Identifier for the store
    store_name: str  # Name of the store
    terminal_no: Optional[int] = None  # Terminal number (None for store-level reports)
    business_counter: Optional[int] = None  # Business counter for the day
    business_date: Optional[str] = None  # Date for which the report is generated (None for date range)
    business_date_from: Optional[str] = None  # Start date for date range reports
    business_date_to: Optional[str] = None  # End date for date range reports
    open_counter: Optional[int] = None  # Counter for terminal open/close cycles
    report_scope: str  # Scope of the report (e.g., 'flash', 'daily')
    report_type: str  # Type of report (e.g., 'sales')
    sales_gross: SalesReportTemplate  # Gross sales data
    sales_net: SalesReportTemplate  # Net sales data
    discount_for_lineitems: SalesReportTemplate  # Item-level discounts
    discount_for_subtotal: SalesReportTemplate  # Subtotal-level discounts
    returns: SalesReportTemplate  # Return transaction data
    taxes: list[TaxReportTemplate]  # List of tax data
    payments: list[PaymentReportTemplate]  # List of payment method data
    cash: CashReportTemplate  # Cash drawer data
    receipt_text: Optional[str] = None  # Formatted text for receipt printing
    journal_text: Optional[str] = None  # Formatted text for journal
    generate_date_time: str  # Date and time when the report was generated
    staff: Optional[StaffMasterDocument] = None  # Staff who generated the report

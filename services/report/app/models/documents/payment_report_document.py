# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional, List

from pydantic import Field
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel
from app.models.documents.sales_report_document import PaymentVariantReport


class PaymentReportDocument(AbstractDocument):
    """
    Document model representing a payment method report.
    
    This class defines the structure for storing aggregated payment data by payment method.
    It provides detailed insights into payment method usage including transaction counts,
    amounts, and composition ratios.
    """
    
    class PaymentSummaryItem(BaseDocumentModel):
        """
        Represents aggregated data for a specific payment method.
        
        Contains metrics for a single payment method including
        transaction counts, amounts, and composition ratio.
        """
        payment_code: str
        payment_name: str
        count: int  # Number of transactions
        amount: float  # Total amount
        ratio: float  # Composition ratio (percentage)
        # Breakdown by variant (issue #311); counts are of transactions, so one
        # transaction that used two variants counts once under each
        variants: List[PaymentVariantReport] = Field(default_factory=list)
    
    class PaymentTotal(BaseDocumentModel):
        """
        Represents total aggregated payment data.
        
        Contains total counts and amounts across all payment methods.
        """
        count: int  # Total transaction count
        amount: float  # Total amount
    
    # Report metadata
    tenant_id: str
    store_code: str
    store_name: Optional[str] = None
    terminal_no: Optional[int] = None
    business_date: Optional[str] = None  # Optional for date range reports
    business_date_from: Optional[str] = None  # For date range reports
    business_date_to: Optional[str] = None    # For date range reports
    open_counter: Optional[int] = None
    business_counter: Optional[int] = None
    report_scope: str  # "flash" or "daily"
    report_type: str = "payment"
    
    # Payment data
    payment_summary: List[PaymentSummaryItem] = []
    
    # Summary totals
    total: PaymentTotal
    
    # Output formats
    receipt_text: Optional[str] = None
    journal_text: Optional[str] = None
    # Daily reports only: what had not arrived when the sessions were settled (#343)
    missing_count: Optional[int] = None
    missing_ranges: Optional[list[dict]] = None  # [{terminal_no, business_date, business_counter, first, last}]
    generate_date_time: Optional[str] = None
    staff: Optional[dict] = None
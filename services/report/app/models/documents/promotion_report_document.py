# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel


class PromotionReportDocument(AbstractDocument):
    """
    Document model representing a promotion performance report.

    This class defines the structure for storing aggregated sales data grouped by promotions.
    It provides insights into promotion effectiveness including discount amounts, quantities,
    and transaction counts.
    """

    class PromotionReportItem(BaseDocumentModel):
        """
        Represents performance data for a specific promotion.

        Contains aggregated metrics for a single promotion including
        discount amounts, affected quantities, and transaction counts.
        """

        promotion_code: Optional[str] = None
        promotion_type: Optional[str] = None
        gross_amount: Optional[float] = 0.0  # Total sales before discount
        discount_amount: Optional[float] = 0.0  # Total discount given
        net_amount: Optional[float] = 0.0  # Sales after discount
        quantity: Optional[int] = 0  # Number of items discounted
        transaction_count: Optional[int] = 0  # Number of transactions with this promotion

    # Report metadata
    tenant_id: Optional[str] = None
    store_code: Optional[str] = None
    store_name: Optional[str] = None
    terminal_no: Optional[int] = None
    business_date: Optional[str] = None  # Single date (None for date range)
    business_date_from: Optional[str] = None  # Start date for date range reports
    business_date_to: Optional[str] = None  # End date for date range reports
    open_counter: Optional[int] = None
    business_counter: Optional[int] = None
    report_scope: Optional[str] = None  # "flash" or "daily"
    report_type: Optional[str] = "promotion"

    # Promotion data
    promotions: Optional[list[PromotionReportItem]] = []

    # Summary totals
    total_gross_amount: Optional[float] = 0.0
    total_discount_amount: Optional[float] = 0.0
    total_net_amount: Optional[float] = 0.0
    total_quantity: Optional[int] = 0
    total_transaction_count: Optional[int] = 0

    # Output formats
    receipt_text: Optional[str] = None
    journal_text: Optional[str] = None
    generate_date_time: Optional[str] = None
    staff: Optional[dict] = None

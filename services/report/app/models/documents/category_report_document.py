# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.documents.base_document_model import BaseDocumentModel


class CategoryReportDocument(AbstractDocument):
    """
    Document model representing a category-based sales report.
    
    This class defines the structure for storing aggregated sales data grouped by product categories.
    It provides insights into sales performance across different product categories, including
    gross sales, discounts, net sales, quantities, and total amounts.
    """
    
    class CategoryReportItem(BaseDocumentModel):
        """
        Represents sales data for a specific category.
        
        Contains aggregated metrics for a single product category including
        sales amounts, discounts, and quantities.
        """
        category_code: Optional[str] = None
        category_name: Optional[str] = None
        gross_amount: Optional[float] = 0.0  # 総売上
        discount_amount: Optional[float] = 0.0  # 値引
        net_amount: Optional[float] = 0.0  # 純売上
        quantity: Optional[int] = 0  # 点数
        discount_quantity: Optional[int] = 0  # 値引点数
        transaction_count: Optional[int] = 0  # 売上件数
    
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
    report_type: Optional[str] = "category"
    
    # Category data
    categories: Optional[list[CategoryReportItem]] = []
    
    # Summary totals
    total_gross_amount: Optional[float] = 0.0
    total_discount_amount: Optional[float] = 0.0
    total_net_amount: Optional[float] = 0.0
    total_quantity: Optional[int] = 0
    total_discount_quantity: Optional[int] = 0
    total_transaction_count: Optional[int] = 0
    
    # Output formats
    receipt_text: Optional[str] = None
    journal_text: Optional[str] = None
    generate_date_time: Optional[str] = None
    staff: Optional[dict] = None
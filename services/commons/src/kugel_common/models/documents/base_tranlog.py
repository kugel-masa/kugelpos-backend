# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Optional, Dict, Any
from pydantic import ConfigDict

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel
from kugel_common.models.documents.user_info_document import UserInfoDocument

class BaseTransaction(AbstractDocument):
    """
    Base transaction document model for POS transactions.
    
    This class extends AbstractDocument to provide a comprehensive data structure for storing
    all transaction-related information, including sales details, line items, payments,
    taxes, and discounts. It serves as the foundation for the transaction logging system.
    """

    class SalesInfo(BaseDocumentModel):
        """
        Nested class representing sales summary information for a transaction.
        
        Contains aggregated information about transaction amounts, taxes, quantities,
        change amounts, and discount totals.
        """
        reference_date_time: Optional[str] = None
        total_amount: Optional[float] = 0.0
        total_amount_with_tax: Optional[float] = 0.0
        tax_amount: Optional[float] = 0.0
        total_quantity: Optional[int] = 0
        change_amount: Optional[float] = 0.0
        total_discount_amount: Optional[float] = 0.0
        is_cancelled: Optional[bool] = False
        is_stamp_duty_applied: Optional[bool] = False
        stamp_duty_target_amount: Optional[float] = 0.0
        stamp_duty_amount: Optional[float] = 0.0

    class Payment(BaseDocumentModel):
        """
        Nested class representing payment information for a transaction.
        
        Contains details about a specific payment method used in the transaction,
        including payment amount and deposit details.
        """
        payment_no: Optional[int] = None
        payment_code: Optional[str] = None
        deposit_amount: Optional[float] = 0.0
        amount: Optional[float] = 0.0
        description: Optional[str] = None
        detail: Optional[str] = None

    class DiscountInfo(BaseDocumentModel):
        """
        Nested class representing discount information for a transaction.
        
        Contains details about discounts applied to line items or the entire transaction.
        """
        seq_no: Optional[int] = None
        discount_type: Optional[str] = None
        discount_value: Optional[float] = 0.0
        discount_amount: Optional[float] = 0.0
        detail: Optional[str] = None

    class LineItem(BaseDocumentModel):
        """
        Nested class representing a line item in a transaction.
        
        Contains detailed information about a product or service included in the transaction,
        including pricing, quantity, and applied discounts.
        """
        line_no: Optional[int] = None
        item_code: Optional[str] = None
        category_code: Optional[str] = None
        description: Optional[str] = None
        description_short: Optional[str] = None
        unit_price: Optional[float] = 0.0
        unit_price_original: Optional[float] = 0.0
        is_unit_price_changed: Optional[bool] = False
        quantity: Optional[int] = 0
        discounts: Optional[list["BaseTransaction.DiscountInfo"]] = []
        discounts_allocated: Optional[list["BaseTransaction.DiscountInfo"]] = []
        amount: Optional[float] = 0.0
        tax_code: Optional[str] = None
        is_cancelled: Optional[bool] = False
    
    class Tax(BaseDocumentModel):
        """
        Nested class representing tax information for a transaction.
        
        Contains details about taxes calculated for the transaction,
        including tax rates, amounts, and applicable bases.
        """
        tax_no: Optional[int] = None
        tax_code: Optional[str] = None
        tax_type: Optional[str] = None
        tax_name: Optional[str] = None
        tax_amount: Optional[float] = 0.0
        target_amount: Optional[float] = 0.0
        target_quantity: Optional[int] = 0
    
    class Staff(BaseDocumentModel):
        """
        Nested class representing staff information associated with a transaction.
        
        Contains basic identification of the staff member who processed the transaction.
        """
        id: Optional[str] = None
        name: Optional[str] = None
    
    class OriginalTransaction(BaseDocumentModel):
        """
        Nested class representing the original transaction information for returns and voids.
        
        Contains reference information to the original transaction being modified,
        used for return, void, and cancellation transactions.
        """
        generate_date_time: Optional[str] = None
        tenant_id: Optional[str] = None
        store_code: Optional[str] = None
        store_name: Optional[str] = None
        terminal_no: Optional[int] = None
        transaction_no: Optional[int] = None
        transaction_type: Optional[int] = None
        receipt_no: Optional[int] = None
    
    # Transaction metadata
    tenant_id: Optional[str] = None
    store_code: Optional[str] = None
    store_name: Optional[str] = None
    terminal_no: Optional[int] = None
    transaction_no: Optional[int] = None
    transaction_type: Optional[int] = None
    business_date: Optional[str] = None  # format:YYYYMMDD
    open_counter: Optional[int] = None
    business_counter: Optional[int] = None
    generate_date_time: Optional[str] = None
    receipt_no: Optional[int] = None
    user: Optional[UserInfoDocument] = None
    sales: Optional[SalesInfo] = None

    # Transaction details
    line_items: Optional[list[LineItem]] = []
    payments: Optional[list[Payment]] = []
    taxes: Optional[list[Tax]] = []
    subtotal_discounts: Optional[list[DiscountInfo]] = []
    origin: Optional[OriginalTransaction] = None
    staff: Optional[Staff] = None
    receipt_text: Optional[str] = None
    journal_text: Optional[str] = None
    # Optional fields
    additional_info: Optional[Dict[str, Any]] = None
    
    # Transaction status flags
    is_voided: Optional[bool] = False
    is_refunded: Optional[bool] = False

    # camel case
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)
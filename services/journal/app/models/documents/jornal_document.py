# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from datetime import datetime

from kugel_common.models.documents.abstract_document import AbstractDocument


class JournalDocument(AbstractDocument):
    """
    Document class representing a journal entry.

    This class stores information about transaction journal entries, including
    details about the transaction, business dates, and formatted text for both
    the journal and receipt. It serves as a permanent record of all POS operations.
    """

    tenant_id: str  # Identifier for the tenant
    store_code: str  # Identifier for the store
    terminal_no: int  # Terminal number
    transaction_no: Optional[int] = None  # Transaction number if applicable
    transaction_type: int  # Type of transaction
    business_date: str  # Business date for the transaction
    open_counter: int  # Counter for terminal open/close cycles
    business_counter: int  # Business counter for the day
    receipt_no: Optional[int] = None  # Receipt number if applicable
    amount: Optional[float] = 0.0  # Transaction amount
    quantity: Optional[int] = 0  # Quantity of items in the transaction
    staff_id: Optional[str] = None  # ID of staff performing the transaction
    user_id: Optional[str] = None  # User ID if applicable
    generate_date_time: str  # Date and time when the journal was generated
    journal_text: str  # Formatted text for journal
    receipt_text: str  # Formatted text for receipt printing

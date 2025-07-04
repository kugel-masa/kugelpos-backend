# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument


class CashInOutLog(AbstractDocument):
    """
    Cash In/Out Log Document

    This class represents a cash drawer transaction record in the POS system.
    It tracks all cash additions and removals from the terminal's cash drawer,
    including initial amounts, cash deposits, and withdrawals.

    Each record is associated with a specific terminal, staff member, and business date.
    """

    tenant_id: Optional[str] = None  # Tenant ID that owns this record
    store_code: Optional[str] = None  # Store code where the transaction occurred
    store_name: Optional[str] = None  # Name of the store for display purposes
    terminal_no: Optional[int] = None  # Terminal number that processed the transaction
    staff_id: Optional[str] = None  # ID of the staff member who performed the transaction
    staff_name: Optional[str] = None  # Name of the staff member for display purposes
    business_date: Optional[str] = None  # Business date when the transaction occurred (YYYYMMDD)
    open_counter: Optional[int] = None  # Terminal open counter when the transaction occurred
    business_counter: Optional[int] = None  # Business counter when the transaction occurred
    generate_date_time: Optional[str] = None  # Timestamp when the transaction was generated
    amount: Optional[float] = None  # Amount of cash added (positive) or removed (negative)
    description: Optional[str] = None  # Description or reason for the cash movement
    receipt_text: Optional[str] = None  # Formatted text for receipts
    journal_text: Optional[str] = None  # Formatted text for journal entries

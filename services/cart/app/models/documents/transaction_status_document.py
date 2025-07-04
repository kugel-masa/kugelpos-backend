# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
Transaction status tracking document for void/return history
"""
from typing import Optional
from kugel_common.models.documents.abstract_document import AbstractDocument


class TransactionStatusDocument(AbstractDocument):
    """
    Document to track void/return status of transactions

    This collection maintains the history of void/return operations
    without modifying the original transaction data.
    """

    # Transaction identifiers
    tenant_id: str
    store_code: str
    terminal_no: int
    transaction_no: int

    # Status flags
    is_voided: bool = False
    is_refunded: bool = False

    # Void information
    void_transaction_no: Optional[int] = None
    void_date_time: Optional[str] = None
    void_staff_id: Optional[str] = None

    # Return information
    return_transaction_no: Optional[int] = None
    return_date_time: Optional[str] = None
    return_staff_id: Optional[str] = None

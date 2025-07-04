# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from app.models.documents.abstract_document import AbstractDocument
from typing import Optional


class PaymentMasterDocument(AbstractDocument):
    """
    Document class representing payment method configurations in the master data system.

    This class defines the attributes and behaviors of different payment methods used
    in the POS system, such as cash, credit card, or gift cards. It includes
    configuration for payment limits, refund capabilities, and change handling.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    payment_code: Optional[str] = None  # Unique code identifying this payment method
    description: Optional[str] = None  # Description of the payment method
    limit_amount: Optional[float] = 0.0  # Maximum amount allowed for this payment method
    can_refund: Optional[bool] = True  # Flag indicating if this payment method can be used for refunds
    can_deposit_over: Optional[bool] = (
        False  # Flag indicating if this payment method can accept deposits exceeding the transaction amount
    )
    can_change: Optional[bool] = False  # Flag indicating if this payment method can provide change
    is_active: Optional[bool] = True  # Flag indicating if this payment method is currently active

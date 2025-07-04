# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from pydantic import ConfigDict

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.misc import to_lower_camel


class PaymentMasterDocument(AbstractDocument):
    """
    Document model representing payment method master data.

    This class defines the structure for storing payment method information
    including type, limits, and various capabilities.
    """

    tenant_id: Optional[str] = None  # Identifier for the tenant
    store_code: Optional[str] = None  # Code identifying the store
    payment_code: Optional[str] = None  # Unique identifier for the payment method
    description: Optional[str] = None  # Description of the payment method
    limit_amount: Optional[float] = 0.0  # Maximum amount allowed for this payment method
    can_refund: Optional[bool] = True  # Flag indicating if refunds are allowed
    can_deposit_over: Optional[bool] = False  # Flag indicating if over-payment is allowed
    can_change: Optional[bool] = False  # Flag indicating if change can be given
    is_active: Optional[bool] = True  # Flag indicating if the payment method is active

    # Configuration for Pydantic model to use camelCase field names in JSON
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

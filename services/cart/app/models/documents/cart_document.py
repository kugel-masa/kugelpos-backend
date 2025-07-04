# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.documents.base_tranlog import BaseTransaction
from app.models.documents.item_master_document import ItemMasterDocument
from app.models.documents.tax_master_document import TaxMasterDocument
from app.models.documents.settings_master_document import SettingsMasterDocument


class CartDocument(BaseTransaction):
    """
    Document model representing a shopping cart.

    This class extends BaseTransaction and defines the structure for storing cart data
    including line items, totals, and reference to master data documents.
    """

    class CartLineItem(BaseTransaction.LineItem):
        """
        Represents an item in the shopping cart.

        Extends the base LineItem class with additional cart-specific attributes.
        """

        item_details: Optional[list[str]] = []  # Additional details about the item
        image_urls: Optional[list[str]] = []  # URLs to item images
        is_discount_restricted: Optional[bool] = False  # Flag indicating if discounts can be applied

    class ReferenceMasters(BaseDocumentModel):
        """
        Container for references to master data documents.

        Stores copies of relevant master data documents to avoid additional database lookups.
        """

        items: Optional[list[ItemMasterDocument]] = []  # Item master data
        taxes: Optional[list[TaxMasterDocument]] = []  # Tax configuration
        settings: Optional[list[SettingsMasterDocument]] = []  # System settings

    cart_id: Optional[str] = None  # Unique identifier for the cart
    status: Optional[str] = None  # Current status of the cart (e.g., active, completed, abandoned)
    subtotal_amount: Optional[float] = 0.0  # Sum of line items before tax and discounts
    balance_amount: Optional[float] = 0.0  # Final amount after all calculations
    line_items: Optional[list[CartLineItem]] = []  # Items in the cart
    masters: Optional[ReferenceMasters] = ReferenceMasters()  # References to master data

# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from app.models.documents.item_common_master_document import ItemCommonMasterDocument


class ItemStoreDetailDocument(ItemCommonMasterDocument):
    """
    Document class representing combined item details with store-specific overrides.

    This class extends the common item master document to include store-specific
    information such as store code and store-specific pricing. It is used to provide
    a complete view of an item with store-specific overrides applied.
    """

    store_code: Optional[str] = None  # Identifier for the specific store
    store_price: Optional[float] = None  # Store-specific price that overrides the standard unit price

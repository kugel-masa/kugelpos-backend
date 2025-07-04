# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from typing import Optional
from pydantic import Field

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from app.models.documents.abstract_document import AbstractDocument
from app.enums.button_size import ButtonSize


class ItemBookButton(BaseDocumentModel):
    """
    Represents a button in the item book UI that is linked to a specific product.

    Each button has a position, size, visual styling, and is associated with a specific
    item code. The button can display price and description information retrieved
    dynamically from the item master.
    """

    pos_x: Optional[int] = None  # X-coordinate position of the button in the grid
    pos_y: Optional[int] = None  # Y-coordinate position of the button in the grid
    size: Optional[ButtonSize] = None  # Size of the button (e.g., SMALL, MEDIUM, LARGE)
    image_url: Optional[str] = None  # URL to the image displayed on the button
    color_text: Optional[str] = None  # Color code for the button's text
    item_code: Optional[str] = None  # Reference to the associated item
    unit_price: Optional[float] = Field(None, exclude=True)  # Price of the item, not stored but retrieved dynamically
    description: Optional[str] = Field(
        None, exclude=True
    )  # Description of the item, not stored but retrieved dynamically


class ItemBookTab(BaseDocumentModel):
    """
    Represents a tab within a category in the item book UI.

    Tabs are used to organize buttons into logical groups within a category,
    creating a hierarchical navigation structure for accessing products.
    """

    tab_number: Optional[int] = None  # Sequential number identifying this tab within its category
    title: Optional[str] = None  # Display title for the tab
    color: Optional[str] = None  # Color code for the tab's visual styling
    buttons: Optional[list[ItemBookButton]] = None  # List of buttons contained within this tab


class ItemBookCategory(BaseDocumentModel):
    """
    Represents a top-level category within the item book UI.

    Categories are the highest level of organization in the item book hierarchy,
    containing tabs which in turn contain buttons linked to specific products.
    """

    category_number: Optional[int] = None  # Sequential number identifying this category within the item book
    title: Optional[str] = None  # Display title for the category
    color: Optional[str] = None  # Color code for the category's visual styling
    tabs: Optional[list[ItemBookTab]] = None  # List of tabs contained within this category


class ItemBookMasterDocument(AbstractDocument):
    """
    Main document class representing an item book in the master data system.

    An item book is a hierarchical structure for organizing products in the POS UI,
    consisting of categories, tabs, and buttons. This structure facilitates efficient
    product selection during the sales process and can be customized for different
    stores or departments.
    """

    tenant_id: Optional[str] = None  # Unique identifier for the tenant (multi-tenancy support)
    item_book_id: Optional[str] = None  # Unique identifier for this item book
    title: Optional[str] = None  # Display title for the item book
    categories: Optional[list[ItemBookCategory]] = None  # List of categories contained in this item book

# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.models.documents.cart_document import CartDocument
from app.models.repositories.tax_master_repository import TaxMasterRepository
from app.services.logics import calc_subtotal_logic
from kugel_common.models.documents.base_tranlog import BaseTransaction
from kugel_common.enums import TaxType


class TestCalcSubtotalLogic:
    """Test suite for calc_subtotal_logic module."""

    @pytest.fixture
    def cart_doc(self):
        """Create a sample cart document for testing."""
        cart = CartDocument()
        cart.sales = BaseTransaction.SalesInfo()

        # Add line items
        item1 = CartDocument.CartLineItem()
        item1.line_no = 1
        item1.unit_price = 100.0
        item1.quantity = 2
        item1.amount = 200.0
        item1.is_cancelled = False
        item1.discounts = []

        item2 = CartDocument.CartLineItem()
        item2.line_no = 2
        item2.unit_price = 50.0
        item2.quantity = 1
        item2.amount = 50.0
        item2.is_cancelled = False
        item2.discounts = [BaseTransaction.DiscountInfo(discount_amount=5.0)]

        cart.line_items = [item1, item2]
        cart.subtotal_discounts = []
        cart.taxes = []
        cart.payments = []

        return cart

    @pytest.fixture
    def tax_master_repo(self):
        """Create a mock tax master repository."""
        return MagicMock(spec=TaxMasterRepository)

    @pytest.mark.asyncio
    @patch("app.services.logics.calc_subtotal_logic.calc_line_item_logic")
    @patch("app.services.logics.calc_subtotal_logic.calc_tax_logic")
    async def test_calc_subtotal_async(self, mock_calc_tax, mock_calc_line_item, cart_doc, tax_master_repo):
        """Test the main calc_subtotal_async function."""
        # Setup mocks
        mock_calc_line_item.calc_line_item_async = AsyncMock(side_effect=lambda x: x)
        mock_calc_tax.calc_tax_async = AsyncMock(return_value=cart_doc)

        # Add some taxes to the cart
        cart_doc.taxes = [
            BaseTransaction.Tax(tax_amount=25.0, tax_type=TaxType.External.value),
            BaseTransaction.Tax(tax_amount=5.0, tax_type=TaxType.Internal.value),
        ]

        # Execute
        result = await calc_subtotal_logic.calc_subtotal_async(cart_doc, tax_master_repo)

        # Verify line item calculation was called for non-cancelled items
        assert mock_calc_line_item.calc_line_item_async.call_count == 2

        # Verify tax calculation was called
        mock_calc_tax.calc_tax_async.assert_called_once_with(cart_doc, tax_master_repo)

        # Verify sales info was updated
        assert result.sales.total_discount_amount == 5.0  # From line item discount
        assert (
            result.sales.total_amount == 250.0
        )  # 250 - 0 (no subtotal discounts, line item discounts don't affect total_amount)
        assert result.sales.tax_amount == 25.0  # External tax only
        assert result.sales.total_quantity == 3  # 2 + 1
        assert result.sales.total_amount_with_tax == 275.0  # 250 + 25
        assert result.balance_amount == 275.0  # No payments

    @pytest.mark.asyncio
    async def test_update_sales_info_async_with_discounts(self):
        """Test update_sales_info_async with various discounts."""
        cart = CartDocument()
        cart.sales = BaseTransaction.SalesInfo()

        # Setup line items with discounts
        item1 = CartDocument.CartLineItem()
        item1.amount = 100.0
        item1.quantity = 1
        item1.is_cancelled = False
        item1.discounts = [
            BaseTransaction.DiscountInfo(discount_amount=10.0),
            BaseTransaction.DiscountInfo(discount_amount=5.0),
        ]

        item2 = CartDocument.CartLineItem()
        item2.amount = 50.0
        item2.quantity = 2
        item2.is_cancelled = False
        item2.discounts = []

        cart.line_items = [item1, item2]

        # Add subtotal discounts
        cart.subtotal_discounts = [
            BaseTransaction.DiscountInfo(discount_amount=20.0),
            BaseTransaction.DiscountInfo(discount_amount=10.0),
        ]

        # Add taxes
        cart.taxes = [
            BaseTransaction.Tax(tax_amount=12.0, tax_type=TaxType.External.value),
            BaseTransaction.Tax(tax_amount=3.0, tax_type=TaxType.Internal.value),
        ]

        # Add payment
        cart.payments = [BaseTransaction.Payment(amount=100.0)]

        # Execute
        result = await calc_subtotal_logic.update_sales_info_async(cart)

        # Verify calculations
        assert result.sales.total_discount_amount == 45.0  # 30 (subtotal) + 15 (line items)
        assert result.subtotal_amount == 150.0  # 100 + 50
        assert result.sales.total_amount == 120.0  # 150 - 30 (subtotal discounts)
        assert result.sales.tax_amount == 12.0  # External tax only
        assert result.sales.total_quantity == 3  # 1 + 2
        assert result.sales.total_amount_with_tax == 132.0  # 120 + 12
        assert result.balance_amount == 32.0  # 132 - 100

    @pytest.mark.asyncio
    async def test_update_sales_info_async_with_cancelled_items(self):
        """Test that cancelled items are excluded from calculations."""
        cart = CartDocument()
        cart.sales = BaseTransaction.SalesInfo()

        # Setup line items with one cancelled
        item1 = CartDocument.CartLineItem()
        item1.amount = 100.0
        item1.quantity = 1
        item1.is_cancelled = False
        item1.discounts = []

        item2 = CartDocument.CartLineItem()
        item2.amount = 50.0
        item2.quantity = 2
        item2.is_cancelled = True  # Cancelled
        item2.discounts = [BaseTransaction.DiscountInfo(discount_amount=5.0)]

        cart.line_items = [item1, item2]
        cart.subtotal_discounts = []
        cart.taxes = []
        cart.payments = []

        # Execute
        result = await calc_subtotal_logic.update_sales_info_async(cart)

        # Verify only non-cancelled items are included
        assert result.sales.total_discount_amount == 0.0  # Cancelled item discount not counted
        assert result.subtotal_amount == 100.0  # Only item1
        assert result.sales.total_amount == 100.0
        assert result.sales.total_quantity == 1  # Only item1
        assert result.balance_amount == 100.0

    @pytest.mark.asyncio
    async def test_update_sales_info_async_empty_cart(self):
        """Test calculations with an empty cart."""
        cart = CartDocument()
        cart.sales = BaseTransaction.SalesInfo()
        cart.line_items = []
        cart.subtotal_discounts = []
        cart.taxes = []
        cart.payments = []

        # Execute
        result = await calc_subtotal_logic.update_sales_info_async(cart)

        # Verify all amounts are zero
        assert result.sales.total_discount_amount == 0.0
        assert result.subtotal_amount == 0.0
        assert result.sales.total_amount == 0.0
        assert result.sales.tax_amount == 0.0
        assert result.sales.total_quantity == 0
        assert result.sales.total_amount_with_tax == 0.0
        assert result.balance_amount == 0.0

    @pytest.mark.asyncio
    @patch("app.services.logics.calc_subtotal_logic.calc_line_item_logic")
    async def test_calc_subtotal_skips_cancelled_items(self, mock_calc_line_item, cart_doc, tax_master_repo):
        """Test that cancelled items are skipped in line item calculation."""
        # Setup mock
        mock_calc_line_item.calc_line_item_async = AsyncMock(side_effect=lambda x: x)

        # Make one item cancelled
        cart_doc.line_items[1].is_cancelled = True

        # Execute
        with patch(
            "app.services.logics.calc_subtotal_logic.calc_tax_logic.calc_tax_async", AsyncMock(return_value=cart_doc)
        ):
            await calc_subtotal_logic.calc_subtotal_async(cart_doc, tax_master_repo)

        # Verify calc_line_item was only called for non-cancelled item
        assert mock_calc_line_item.calc_line_item_async.call_count == 1

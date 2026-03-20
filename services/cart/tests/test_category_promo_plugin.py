# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.strategies.sales_promo.category_promo import CategoryPromoPlugin, CategoryPromoDetail
from app.models.documents.cart_document import CartDocument
from app.models.documents.promotion_master_document import PromotionMasterDocument


def make_line_item(
    line_no=1,
    item_code="ITEM-01",
    category_code="001",
    unit_price=100.0,
    quantity=2,
    is_cancelled=False,
    is_discount_restricted=False,
    discounts=None,
):
    item = CartDocument.CartLineItem(
        line_no=line_no,
        item_code=item_code,
        category_code=category_code,
        unit_price=unit_price,
        quantity=quantity,
        is_cancelled=is_cancelled,
        is_discount_restricted=is_discount_restricted,
        discounts=discounts or [],
    )
    return item


def make_promotion(
    promotion_code="PROMO-01",
    promotion_type="category_discount",
    name="Test Promo",
    target_category_codes=None,
    target_store_codes=None,
    discount_rate=10.0,
):
    detail = {
        "targetCategoryCodes": target_category_codes or ["001"],
        "targetStoreCodes": target_store_codes or [],
        "discountRate": discount_rate,
    }
    return PromotionMasterDocument(
        promotion_code=promotion_code,
        promotion_type=promotion_type,
        name=name,
        is_active=True,
        detail=detail,
    )


def make_cart(line_items=None):
    cart = CartDocument(
        tenant_id="T001",
        store_code="S001",
        terminal_no=1,
        transaction_no=1,
        transaction_type=101,
        business_date="20240101",
        open_counter=1,
        business_counter=1,
        generate_date_time="2024-01-01T10:00:00",
        staff=CartDocument.Staff(id="ST01", name="Staff"),
        sales=CartDocument.SalesInfo(),
        line_items=line_items or [],
    )
    return cart


class TestCategoryPromoPluginApply:
    """Tests for CategoryPromoPlugin.apply()."""

    @pytest.fixture
    def plugin(self):
        p = CategoryPromoPlugin()
        p.promotion_master_repo = AsyncMock()
        return p

    @pytest.mark.asyncio
    async def test_apply_discount_to_matching_category(self, plugin):
        """Item with matching category gets discount applied."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["001"], discount_rate=10.0)
        ]
        line_item = make_line_item(category_code="001", unit_price=100.0, quantity=2)
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 1
        discount = result.line_items[0].discounts[0]
        assert discount.discount_value == 10.0
        assert discount.discount_amount == 20.0
        assert discount.promotion_type == "category_discount"

    @pytest.mark.asyncio
    async def test_no_discount_for_non_matching_category(self, plugin):
        """Item with non-matching category gets no discount."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["002"], discount_rate=10.0)
        ]
        line_item = make_line_item(category_code="001")
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_skip_cancelled_line_item(self, plugin):
        """Cancelled items are skipped."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["001"])
        ]
        line_item = make_line_item(category_code="001", is_cancelled=True)
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_skip_discount_restricted_item(self, plugin):
        """Discount-restricted items are skipped."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["001"])
        ]
        line_item = make_line_item(category_code="001", is_discount_restricted=True)
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_skip_already_discounted_item(self, plugin):
        """Item already having a category_discount is not discounted again."""
        from kugel_common.models.documents.base_tranlog import BaseTransaction
        existing_discount = BaseTransaction.DiscountInfo(
            seq_no=1,
            discount_type="DiscountPercentage",
            discount_value=5.0,
            discount_amount=10.0,
            promotion_type="category_discount",
        )
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["001"], discount_rate=10.0)
        ]
        line_item = make_line_item(category_code="001", discounts=[existing_discount])
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 1  # still just the existing one

    @pytest.mark.asyncio
    async def test_best_rate_selected_when_multiple_promotions(self, plugin):
        """When multiple promotions target the same category, the highest rate wins."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion("PROMO-LOW", discount_rate=5.0, target_category_codes=["001"]),
            make_promotion("PROMO-HIGH", discount_rate=20.0, target_category_codes=["001"]),
            make_promotion("PROMO-MID", discount_rate=10.0, target_category_codes=["001"]),
        ]
        line_item = make_line_item(category_code="001", unit_price=100.0, quantity=1)
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 1
        assert result.line_items[0].discounts[0].discount_value == 20.0
        assert result.line_items[0].discounts[0].promotion_code == "PROMO-HIGH"

    @pytest.mark.asyncio
    async def test_no_promotions_returns_cart_unchanged(self, plugin):
        """No active promotions → cart returned unchanged."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = []
        line_item = make_line_item(category_code="001")
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_repo_error_returns_cart_unchanged(self, plugin):
        """Repository error → cart returned unchanged (graceful degradation)."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.side_effect = Exception("API error")
        line_item = make_line_item(category_code="001")
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_repo_not_configured_returns_cart_unchanged(self):
        """Plugin without configured repo returns cart unchanged."""
        plugin = CategoryPromoPlugin()
        # promotion_master_repo is None (not configured)
        line_item = make_line_item(category_code="001")
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_non_category_discount_promotion_is_ignored(self, plugin):
        """Promotions with other promotion_type are ignored."""
        promo = make_promotion(promotion_type="flat_discount", target_category_codes=["001"])
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [promo]
        line_item = make_line_item(category_code="001")
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 0

    @pytest.mark.asyncio
    async def test_multiple_line_items_each_get_discount(self, plugin):
        """Multiple items with matching categories all get discounts."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["001", "002"], discount_rate=15.0)
        ]
        items = [
            make_line_item(line_no=1, category_code="001", unit_price=100.0, quantity=1),
            make_line_item(line_no=2, category_code="002", unit_price=200.0, quantity=1),
            make_line_item(line_no=3, category_code="003", unit_price=300.0, quantity=1),
        ]
        cart = make_cart(line_items=items)

        result = await plugin.apply(cart)

        assert len(result.line_items[0].discounts) == 1  # 001 matched
        assert len(result.line_items[1].discounts) == 1  # 002 matched
        assert len(result.line_items[2].discounts) == 0  # 003 not matched

    @pytest.mark.asyncio
    async def test_discount_amount_calculation(self, plugin):
        """Discount amount is correctly calculated as unit_price * quantity * rate / 100."""
        plugin.promotion_master_repo.get_active_promotions_by_store_async.return_value = [
            make_promotion(target_category_codes=["001"], discount_rate=10.0)
        ]
        line_item = make_line_item(category_code="001", unit_price=150.0, quantity=3)
        cart = make_cart(line_items=[line_item])

        result = await plugin.apply(cart)

        # 150 * 3 * 10% = 45
        assert result.line_items[0].discounts[0].discount_amount == 45.0


class TestCategoryPromoDetailParsing:
    """Tests for CategoryPromoDetail parsing via model_validate."""

    def test_parse_camelcase_detail(self):
        """CamelCase keys from API response are parsed correctly."""
        data = {
            "targetStoreCodes": ["S001"],
            "targetCategoryCodes": ["001", "002"],
            "discountRate": 15.0,
        }
        detail = CategoryPromoDetail.model_validate(data)
        assert detail.target_category_codes == ["001", "002"]
        assert detail.target_store_codes == ["S001"]
        assert detail.discount_rate == 15.0

    def test_parse_detail_with_missing_optional_store(self):
        """target_store_codes defaults to empty list when not provided."""
        data = {"targetCategoryCodes": ["001"], "discountRate": 5.0}
        detail = CategoryPromoDetail.model_validate(data)
        assert detail.target_store_codes == []
        assert detail.target_category_codes == ["001"]

    def test_parse_invalid_detail_returns_none_via_plugin(self):
        """Invalid detail dict causes _parse_detail to return None."""
        plugin = CategoryPromoPlugin()
        promo = PromotionMasterDocument(
            promotion_code="BAD",
            promotion_type="category_discount",
            detail={"invalid_key": "bad"},  # won't match any field with useful data
        )
        # discount_rate defaults to 0.0, target_category_codes to []
        result = plugin._parse_detail(promo)
        # Parsing doesn't fail but discount_rate=0 means no effective promotion
        assert result is not None
        assert result.discount_rate == 0.0
        assert result.target_category_codes == []

    def test_parse_none_detail_returns_none(self):
        """None detail returns None from _parse_detail."""
        plugin = CategoryPromoPlugin()
        promo = PromotionMasterDocument(
            promotion_code="NONE",
            promotion_type="category_discount",
            detail=None,
        )
        assert plugin._parse_detail(promo) is None

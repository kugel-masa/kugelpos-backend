# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger
from typing import Optional

from pydantic import BaseModel, ConfigDict

from kugel_common.utils.misc import to_lower_camel
from app.enums.discount_type import DiscountType
from app.services.strategies.sales_promo.abstract_sales_promo import AbstractSalesPromo
from app.models.repositories.promotion_master_web_repository import PromotionMasterWebRepository
from app.models.documents.cart_document import CartDocument
from app.models.documents.promotion_master_document import PromotionMasterDocument
from kugel_common.models.documents.base_tranlog import BaseTransaction

logger = getLogger(__name__)


class CategoryPromoDetail(BaseModel):
    """
    Plugin-local model for category promotion detail.

    Parsed from the generic detail dict on PromotionMasterDocument.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_lower_camel)

    target_store_codes: Optional[list[str]] = []
    target_category_codes: list[str] = []
    discount_rate: float = 0.0


class CategoryPromoPlugin(AbstractSalesPromo):
    """
    Sales promotion plugin for category-based discounts.

    This plugin applies percentage discounts to cart items based on their category codes.
    When multiple promotions match a category, the highest discount rate is selected
    to provide the best price for the customer.

    The plugin respects the is_discount_restricted flag on line items and will not
    apply promotions to items that have this flag set to True.
    """

    def __init__(self) -> None:
        """Initialize the category promotion plugin."""
        super().__init__()
        self.promotion_master_repo: Optional[PromotionMasterWebRepository] = None

    def configure(self, tenant_id: str, terminal_info) -> None:
        """
        Configure the plugin with a promotion master repository.

        Args:
            tenant_id: The tenant identifier for multi-tenancy
            terminal_info: Terminal information for the current session
        """
        self.promotion_master_repo = PromotionMasterWebRepository(
            tenant_id=tenant_id, terminal_info=terminal_info
        )

    async def apply(self, cart_doc: CartDocument) -> CartDocument:
        """
        Apply category-based promotions to cart items.

        For each line item in the cart:
        1. Skip if is_discount_restricted is True
        2. Skip if already has a category promotion discount applied
        3. Find all promotions matching the item's category
        4. Select the promotion with the highest discount rate (best price)
        5. Apply the discount and record promotion information

        Args:
            cart_doc: The cart document to apply promotions to

        Returns:
            CartDocument: The updated cart document with promotions applied
        """
        if self.promotion_master_repo is None:
            logger.warning("Promotion master repository not set. Skipping category promotions.")
            return cart_doc

        # Get active promotions for the current store
        try:
            active_promotions = await self.promotion_master_repo.get_active_promotions_by_store_async()
        except Exception as e:
            logger.error(f"Failed to get active promotions: {e}")
            return cart_doc

        if not active_promotions:
            logger.debug("No active promotions found")
            return cart_doc

        # Build a mapping of category_code to best promotion (highest discount)
        category_promotions = self._build_category_promotion_map(active_promotions)

        if not category_promotions:
            logger.debug("No category promotions applicable")
            return cart_doc

        # Apply promotions to line items
        for line_item in cart_doc.line_items:
            if line_item.is_cancelled:
                continue

            if line_item.is_discount_restricted:
                logger.debug(
                    f"Line {line_item.line_no}: item {line_item.item_code} is discount restricted"
                )
                continue

            # Skip if already has a category_discount promotion
            if self._has_category_promotion(line_item):
                logger.debug(
                    f"Line {line_item.line_no}: item {line_item.item_code} already has category promotion"
                )
                continue

            # Find matching promotion for this item's category
            best_promotion = category_promotions.get(line_item.category_code)
            if best_promotion is None:
                continue

            # Apply the promotion
            self._apply_promotion_to_line_item(line_item, best_promotion)

        return cart_doc

    def _parse_detail(self, promo: PromotionMasterDocument) -> Optional[CategoryPromoDetail]:
        """
        Parse the generic detail dict into a CategoryPromoDetail model.

        Args:
            promo: The promotion document with a raw detail dict

        Returns:
            CategoryPromoDetail if parsing succeeds, None otherwise
        """
        if promo.detail is None:
            return None
        try:
            return CategoryPromoDetail(**promo.detail)
        except Exception as e:
            logger.warning(f"Failed to parse detail for promotion {promo.promotion_code}: {e}")
            return None

    def _build_category_promotion_map(self, promotions: list) -> dict:
        """
        Build a mapping of category codes to their best promotion.

        For each category, keeps only the promotion with the highest discount rate.

        Args:
            promotions: List of PromotionMasterDocument objects

        Returns:
            dict: Mapping of category_code to (promotion_code, promotion_type, discount_rate)
        """
        category_map = {}

        for promo in promotions:
            if promo.promotion_type != "category_discount":
                continue

            detail = self._parse_detail(promo)
            if detail is None:
                continue

            discount_rate = detail.discount_rate

            for category_code in detail.target_category_codes:
                existing = category_map.get(category_code)
                if existing is None or discount_rate > existing["discount_rate"]:
                    category_map[category_code] = {
                        "promotion_code": promo.promotion_code,
                        "promotion_type": promo.promotion_type,
                        "discount_rate": discount_rate,
                        "name": promo.name,
                    }

        return category_map

    def _has_category_promotion(self, line_item: CartDocument.CartLineItem) -> bool:
        """
        Check if a line item already has a category promotion discount applied.

        Args:
            line_item: The cart line item to check

        Returns:
            bool: True if a category_discount promotion is already applied
        """
        if not line_item.discounts:
            return False

        for discount in line_item.discounts:
            if discount.promotion_type == "category_discount":
                return True

        return False

    def _apply_promotion_to_line_item(
        self, line_item: CartDocument.CartLineItem, promotion_info: dict
    ) -> None:
        """
        Apply a promotion discount to a line item.

        Creates a DiscountInfo record with the promotion details and adds it
        to the line item's discounts list.

        Args:
            line_item: The cart line item to apply the promotion to
            promotion_info: Dict containing promotion_code, promotion_type, discount_rate, name
        """
        discount_rate = promotion_info["discount_rate"]

        # Create discount info (discount_amount is calculated by calc_line_item_logic)
        discount_info = BaseTransaction.DiscountInfo(
            seq_no=len(line_item.discounts) + 1 if line_item.discounts else 1,
            discount_type=DiscountType.DiscountPercentage.value,
            discount_value=discount_rate,
            detail=promotion_info.get("name", "Category Promotion"),
            promotion_code=promotion_info["promotion_code"],
            promotion_type=promotion_info["promotion_type"],
        )

        # Initialize discounts list if needed
        if line_item.discounts is None:
            line_item.discounts = []

        line_item.discounts.append(discount_info)

        logger.info(
            f"Applied promotion {promotion_info['promotion_code']} to line {line_item.line_no}: "
            f"{discount_rate}% discount"
        )

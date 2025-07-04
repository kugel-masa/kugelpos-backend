# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from logging import getLogger

from app.models.documents.staff_master_document import StaffMasterDocument
from app.api.common.schemas import (
    BaseStaffResponse,
    BaseItemResponse,
    BaseItemStoreResponse,
    BaseItemStoreDetailResponse,
    BasePaymentResponse,
    BaseSettingsMasterResponse,
    BaseSettingsMasterValue,
    BaseCategoryMasterResponse,
    BaseItemBookResponse,
    BaseItemBookCategory,
    BaseItemBookTab,
    BaseItemBookButton,
    BaseTaxMasterResponse,
)
from app.models.documents.item_common_master_document import ItemCommonMasterDocument
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from app.models.documents.item_store_detail_document import ItemStoreDetailDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.documents.category_master_document import CategoryMasterDocument
from app.models.documents.item_book_master_document import (
    ItemBookMasterDocument,
    ItemBookCategory,
    ItemBookTab,
    ItemBookButton,
)
from app.models.documents.tax_master_document import TaxMasterDocument

logger = getLogger(__name__)


class SchemasTransformer:

    def __init__(self):
        pass

    def transform_staff(self, staff_doc: StaffMasterDocument) -> BaseStaffResponse:
        return BaseStaffResponse(
            id=staff_doc.id,
            name=staff_doc.name,
            pin=staff_doc.pin,
            roles=staff_doc.roles,
            entry_datetime=staff_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if staff_doc.created_at else None,
            last_update_datetime=staff_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if staff_doc.updated_at else None,
        )

    def transform_item(self, item_doc: ItemCommonMasterDocument) -> BaseItemResponse:
        return BaseItemResponse(
            item_code=item_doc.item_code,
            description=item_doc.description,
            unit_price=item_doc.unit_price,
            unit_cost=item_doc.unit_cost,
            item_details=item_doc.item_details,
            image_urls=item_doc.image_urls,
            category_code=item_doc.category_code,
            tax_code=item_doc.tax_code,
            is_discount_restricted=item_doc.is_discount_restricted,
            is_deleted=item_doc.is_deleted,
            entry_datetime=item_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if item_doc.created_at else None,
            last_update_datetime=item_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if item_doc.updated_at else None,
        )

    def transform_item_store(self, item_store_doc: ItemStoreMasterDocument) -> BaseItemStoreResponse:
        return BaseItemStoreResponse(
            item_code=item_store_doc.item_code,
            store_price=item_store_doc.store_price,
            entry_datetime=(
                item_store_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if item_store_doc.created_at else None
            ),
            last_update_datetime=(
                item_store_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if item_store_doc.updated_at else None
            ),
        )

    def transform_item_store_detail(
        self, item_store_detail_doc: ItemStoreDetailDocument
    ) -> BaseItemStoreDetailResponse:
        return BaseItemStoreDetailResponse(
            item_code=item_store_detail_doc.item_code,
            description=item_store_detail_doc.description,
            unit_price=item_store_detail_doc.unit_price,
            unit_cost=item_store_detail_doc.unit_cost,
            item_details=item_store_detail_doc.item_details,
            image_urls=item_store_detail_doc.image_urls,
            category_code=item_store_detail_doc.category_code,
            tax_code=item_store_detail_doc.tax_code,
            store_price=item_store_detail_doc.store_price,
            is_discount_restricted=item_store_detail_doc.is_discount_restricted,
            is_deleted=item_store_detail_doc.is_deleted,
            entry_datetime=(
                item_store_detail_doc.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if item_store_detail_doc.created_at
                else None
            ),
            last_update_datetime=(
                item_store_detail_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if item_store_detail_doc.updated_at
                else None
            ),
        )

    def transform_payment(self, payment_doc: PaymentMasterDocument) -> BasePaymentResponse:
        return BasePaymentResponse(
            tenant_id=payment_doc.tenant_id,
            payment_code=payment_doc.payment_code,
            description=payment_doc.description,
            limit_amount=payment_doc.limit_amount,
            can_refund=payment_doc.can_refund,
            can_deposit_over=payment_doc.can_deposit_over,
            can_change=payment_doc.can_change,
            is_active=payment_doc.is_active,
            entry_datetime=payment_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if payment_doc.created_at else None,
            last_update_datetime=(
                payment_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if payment_doc.updated_at else None
            ),
        )

    def transform_settings_master(self, settings_doc: SettingsMasterDocument) -> BaseSettingsMasterResponse:
        return BaseSettingsMasterResponse(
            name=settings_doc.name,
            default_value=settings_doc.default_value,
            values=[
                BaseSettingsMasterValue(store_code=value.store_code, terminal_no=value.terminal_no, value=value.value)
                for value in settings_doc.values
            ],
            entry_datetime=settings_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if settings_doc.created_at else None,
            last_update_datetime=(
                settings_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if settings_doc.updated_at else None
            ),
        )

    def transform_category_master(self, category_doc: CategoryMasterDocument) -> BaseCategoryMasterResponse:
        return BaseCategoryMasterResponse(
            category_code=category_doc.category_code,
            description=category_doc.description,
            description_short=category_doc.description_short,
            tax_code=category_doc.tax_code,
            entry_datetime=category_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if category_doc.created_at else None,
            last_update_datetime=(
                category_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if category_doc.updated_at else None
            ),
        )

    def transform_item_book_button(self, item_book_button_doc: ItemBookButton) -> BaseItemBookButton:
        return BaseItemBookButton(
            pos_x=item_book_button_doc.pos_x,
            pos_y=item_book_button_doc.pos_y,
            size=item_book_button_doc.size,
            image_url=item_book_button_doc.image_url,
            color_text=item_book_button_doc.color_text,
            item_code=item_book_button_doc.item_code,
            unit_price=item_book_button_doc.unit_price,
            description=item_book_button_doc.description,
        )

    def transform_item_book_tab(self, item_book_tab_doc: ItemBookTab) -> BaseItemBookTab:
        return BaseItemBookTab(
            tab_number=item_book_tab_doc.tab_number,
            title=item_book_tab_doc.title,
            color=item_book_tab_doc.color,
            buttons=[self.transform_item_book_button(button) for button in item_book_tab_doc.buttons],
        )

    def transform_item_book_category(self, item_book_category_doc: ItemBookCategory) -> BaseItemBookCategory:
        return BaseItemBookCategory(
            category_number=item_book_category_doc.category_number,
            title=item_book_category_doc.title,
            color=item_book_category_doc.color,
            tabs=[self.transform_item_book_tab(tab) for tab in item_book_category_doc.tabs],
        )

    def transform_item_book(self, item_book_doc: ItemBookMasterDocument) -> BaseItemBookResponse:
        logger.debug(f"item_book_doc: {item_book_doc}")
        return BaseItemBookResponse(
            item_book_id=item_book_doc.item_book_id,
            title=item_book_doc.title,
            categories=[self.transform_item_book_category(category) for category in item_book_doc.categories],
            entry_datetime=item_book_doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if item_book_doc.created_at else None,
            last_update_datetime=(
                item_book_doc.updated_at.strftime("%Y-%m-%d %H:%M:%S") if item_book_doc.updated_at else None
            ),
        )

    def transform_tax(self, tax_doc: TaxMasterDocument) -> BaseTaxMasterResponse:
        logger.debug(f"tax_master: {tax_doc}")

        return_tax = BaseTaxMasterResponse(
            tax_code=tax_doc.tax_code,
            tax_type=tax_doc.tax_type,
            tax_name=tax_doc.tax_name,
            rate=tax_doc.rate,
            round_digit=tax_doc.round_digit,
            round_method=tax_doc.round_method,
            entry_datetime=None,
            last_update_datetime=None,
        )

        logger.debug(f"return_tax: {return_tax}")
        return return_tax

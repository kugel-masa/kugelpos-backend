"""Every master's response carries isDeleted (issue #324).

A record without the field, or with None, answers false.
"""

from datetime import datetime

import pytest

from app.api.common.schemas_transformer import SchemasTransformer
from app.models.documents.category_master_document import CategoryMasterDocument
from app.models.documents.item_book_master_document import ItemBookMasterDocument
from app.models.documents.item_common_master_document import ItemCommonMasterDocument
from app.models.documents.item_store_master_document import ItemStoreMasterDocument
from app.models.documents.payment_master_document import PaymentMasterDocument
from app.models.documents.promotion_master_document import PromotionMasterDocument
from app.models.documents.settings_master_document import SettingsMasterDocument
from app.models.documents.staff_master_document import StaffMasterDocument

CASES = [
    ("transform_category_master", CategoryMasterDocument,
     {"category_code": "C1", "description": "C", "description_short": "C", "tax_code": "01"}),
    ("transform_item", ItemCommonMasterDocument,
     {"item_code": "I1", "description": "I", "unit_price": 1.0, "unit_cost": 1.0, "item_details": [],
      "image_urls": [], "category_code": "C1", "tax_code": "01"}),
    ("transform_item_store", ItemStoreMasterDocument, {"item_code": "I1", "store_price": 1.0}),
    ("transform_item_book", ItemBookMasterDocument, {"item_book_id": "B1", "title": "Book"}),
    ("transform_payment", PaymentMasterDocument,
     {"payment_code": "01", "description": "Cash", "limit_amount": 0.0, "can_refund": True,
      "can_deposit_over": True, "can_change": True}),
    ("transform_promotion", PromotionMasterDocument,
     {"promotion_code": "P1", "promotion_type": "category_discount", "name": "P",
      "start_datetime": datetime(2026, 1, 1), "end_datetime": datetime(2026, 12, 31)}),
    ("transform_settings_master", SettingsMasterDocument, {"name": "S1", "default_value": "x", "values": []}),
    ("transform_staff", StaffMasterDocument, {"id": "ST1", "name": "Ann", "roles": []}),
]


@pytest.mark.parametrize("method, document, fields", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("flag, expected", [(True, True), (False, False), (None, False)])
def test_the_response_carries_is_deleted(method, document, fields, flag, expected):
    doc = document(**fields, is_deleted=flag, created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1))

    response = getattr(SchemasTransformer(), method)(doc)

    assert response.is_deleted is expected
    assert response.model_dump(by_alias=True)["isDeleted"] is expected


@pytest.mark.parametrize("method, document, fields", CASES, ids=[c[0] for c in CASES])
def test_a_document_without_the_field_is_not_deleted(method, document, fields):
    doc = document.model_validate({**fields, "created_at": datetime(2026, 1, 1), "updated_at": datetime(2026, 1, 1)})

    assert getattr(SchemasTransformer(), method)(doc).is_deleted is False

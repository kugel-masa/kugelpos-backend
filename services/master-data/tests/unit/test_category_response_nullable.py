"""A category row missing optional columns is returned with nulls, not refused.

``BaseCategoryMasterResponse`` required ``description``, ``description_short``,
``tax_code`` and ``entry_datetime`` as ``str``, while ``CategoryMasterDocument``
allows all of them to be ``None``. Create and update require the three text
columns, so the API itself never writes a null; a row written straight to the
database (a migration, mongoimport, another system) can. Building the response
for such a row raised pydantic's ValidationError, which kugel_common maps to 422.
"""

from datetime import datetime

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.models.documents.category_master_document import CategoryMasterDocument


def test_row_without_short_description_or_tax_code():
    doc = CategoryMasterDocument(
        category_code="01",
        description="Food",
        description_short=None,
        tax_code=None,
        created_at=datetime(2026, 11, 1, 9, 0, 0),
    )

    response = SchemasTransformerV1().transform_category_master(doc)

    assert response.category_code == "01"
    assert response.description == "Food"
    assert response.description_short is None
    assert response.tax_code is None
    assert response.entry_datetime == "2026-11-01 09:00:00"


def test_row_without_created_at():
    doc = CategoryMasterDocument(category_code="02", description="Drink", description_short="Drk", tax_code="01")

    response = SchemasTransformerV1().transform_category_master(doc)

    assert response.entry_datetime is None
    assert response.last_update_datetime is None


def test_complete_row_is_unchanged():
    doc = CategoryMasterDocument(
        category_code="03",
        description="Bakery",
        description_short="Bkr",
        tax_code="02",
        created_at=datetime(2026, 11, 1, 9, 0, 0),
        updated_at=datetime(2026, 11, 2, 10, 30, 0),
    )

    response = SchemasTransformerV1().transform_category_master(doc)

    assert response.model_dump() == {
        "category_code": "03",
        "description": "Bakery",
        "description_short": "Bkr",
        "tax_code": "02",
        "entry_datetime": "2026-11-01 09:00:00",
        "last_update_datetime": "2026-11-02 10:30:00",
    }

# Copyright 2026 masa@kugel
"""An item book button's unit_price and description are display-only.

They come from the item master on /detail and are never stored. These tests
pin the three places that keep it so: the request schemas do not accept them,
a stored book that already carries them (PUT used to $set the request as sent)
does not return them, and /detail can still fill them after loading.
"""
from datetime import datetime

from app.api.common.schemas import BaseItemBookButton, BaseItemBookButtonRequest
from app.api.common.schemas_transformer import SchemasTransformer
from app.api.v1.schemas import ItemBookButton, ItemBookUpdateRequest
from app.models.documents.item_book_master_document import ItemBookButton as ItemBookButtonDocument
from app.models.documents.item_book_master_document import ItemBookMasterDocument


def _stored_book() -> dict:
    """A book as MongoDB holds it after the old PUT: display values included."""
    return {
        "tenant_id": "T1",
        "item_book_id": "BK-1",
        "title": "Menu",
        "created_at": datetime(2026, 1, 1),
        "categories": [{
            "category_number": 1, "title": "c", "color": "#fff",
            "tabs": [{
                "tab_number": 1, "title": "t", "color": "#fff",
                "buttons": [{
                    "pos_x": 0, "pos_y": 0, "size": "Single", "image_url": "", "color_text": "#000",
                    "item_code": "A1", "unit_price": 1.0, "description": "stored",
                }],
            }],
        }],
    }


def _button_request() -> dict:
    return {
        "posX": 0, "posY": 0, "size": "Single", "imageUrl": "", "colorText": "#000",
        "itemCode": "A1", "unitPrice": 9999.0, "description": "sent",
    }


class TestRequestSchemas:
    def test_button_request_has_no_display_fields(self):
        assert "unit_price" not in BaseItemBookButtonRequest.model_fields
        assert "description" not in BaseItemBookButtonRequest.model_fields
        assert "unit_price" not in ItemBookButton.model_fields
        assert "description" not in ItemBookButton.model_fields

    def test_display_fields_sent_are_ignored_not_refused(self):
        button = ItemBookButton.model_validate(_button_request())
        dumped = button.model_dump()
        assert "unit_price" not in dumped
        assert "description" not in dumped
        assert dumped["item_code"] == "A1"

    def test_put_body_drops_display_fields_at_every_level(self):
        body = ItemBookUpdateRequest.model_validate({
            "title": "Menu",
            "categories": [{
                "categoryNumber": 1, "title": "c", "color": "#fff",
                "tabs": [{"tabNumber": 1, "title": "t", "color": "#fff", "buttons": [_button_request()]}],
            }],
        })
        # This dict is what the PUT route hands to the repository's $set.
        stored = body.model_dump()["categories"][0]["tabs"][0]["buttons"][0]
        assert "unit_price" not in stored
        assert "description" not in stored

    def test_response_button_keeps_display_fields(self):
        assert "unit_price" in BaseItemBookButton.model_fields
        assert "description" in BaseItemBookButton.model_fields


class TestStoredBook:
    def test_stored_display_values_are_dropped_on_load(self):
        doc = ItemBookMasterDocument(**_stored_book())
        button = doc.categories[0].tabs[0].buttons[0]
        assert button.unit_price is None
        assert button.description is None
        assert button.item_code == "A1"

    def test_response_built_from_a_stored_book_has_no_display_values(self):
        doc = ItemBookMasterDocument(**_stored_book())
        response = SchemasTransformer().transform_item_book(doc)
        button = response.categories[0].tabs[0].buttons[0]
        assert button.unit_price is None
        assert button.description is None

    def test_detail_can_still_assign_after_load(self):
        """/detail sets the resolved values on the loaded document; assignment is
        not validated, so the load-time normalisation does not undo it."""
        button = ItemBookButtonDocument(item_code="A1", unit_price=1.0, description="stored")
        assert button.unit_price is None
        button.unit_price = 100.0
        button.description = "Real name"
        assert button.unit_price == 100.0
        assert button.description == "Real name"

    def test_display_values_are_never_written(self):
        button = ItemBookButtonDocument(item_code="A1")
        button.unit_price = 100.0
        button.description = "Real name"
        dumped = button.model_dump()
        assert "unit_price" not in dumped
        assert "description" not in dumped

# Copyright 2026 masa@kugel
"""A null child list in an item book means "none", the same as [].

Only [] can be iterated. PUT stored the request as sent, so one "tabs": null
left a book that every read - including the whole list - answered with a 500.
Requests now take null as [], and a null already stored is read as [].
"""
from datetime import datetime

from app.api.common.schemas_transformer import SchemasTransformer
from app.api.v1.schemas import ItemBookCreateRequest, ItemBookUpdateRequest
from app.models.documents.item_book_master_document import (
    ItemBookCategory,
    ItemBookMasterDocument,
    ItemBookTab,
)


def _stored(categories):
    return {"tenant_id": "T1", "item_book_id": "BK-1", "title": "Menu", "created_at": datetime(2026, 1, 1), "categories": categories}


class TestStoredNulls:
    def test_null_categories_read_as_empty(self):
        doc = ItemBookMasterDocument(**_stored(None))
        assert doc.categories == []

    def test_null_tabs_and_buttons_read_as_empty(self):
        doc = ItemBookMasterDocument(**_stored([
            {"category_number": 1, "title": "c", "color": "#fff", "tabs": None},
            {"category_number": 2, "title": "d", "color": "#fff",
             "tabs": [{"tab_number": 1, "title": "t", "color": "#fff", "buttons": None}]},
        ]))
        assert doc.categories[0].tabs == []
        assert doc.categories[1].tabs[0].buttons == []

    def test_a_book_with_stored_nulls_can_be_returned(self):
        doc = ItemBookMasterDocument(**_stored([
            {"category_number": 1, "title": "c", "color": "#fff",
             "tabs": [{"tab_number": 1, "title": "t", "color": "#fff", "buttons": None}]},
        ]))
        response = SchemasTransformer().transform_item_book(doc)
        assert response.categories[0].tabs[0].buttons == []

    def test_defaults_are_empty_lists(self):
        assert ItemBookMasterDocument().categories == []
        assert ItemBookCategory().tabs == []
        assert ItemBookTab().buttons == []


class TestRequestNulls:
    def test_null_lists_in_a_request_become_empty(self):
        body = ItemBookUpdateRequest.model_validate({
            "title": "Menu",
            "categories": [
                {"categoryNumber": 1, "title": "c", "color": "#fff", "tabs": None},
                {"categoryNumber": 2, "title": "d", "color": "#fff",
                 "tabs": [{"tabNumber": 1, "title": "t", "color": "#fff", "buttons": None}]},
            ],
        })
        # This dict is what the PUT route hands to the repository's $set.
        dumped = body.model_dump()
        assert dumped["categories"][0]["tabs"] == []
        assert dumped["categories"][1]["tabs"][0]["buttons"] == []

    def test_null_categories_in_a_request_become_empty(self):
        assert ItemBookCreateRequest.model_validate({"title": "Menu", "categories": None}).categories == []
        assert ItemBookUpdateRequest.model_validate({"title": "Menu", "categories": None}).categories == []

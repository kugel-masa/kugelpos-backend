"""
Unit tests for ItemBookMasterService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kugel_common.exceptions import (
    DocumentNotFoundException,
    DocumentAlreadyExistsException,
    InvalidRequestDataException,
)
from app.services.item_book_master_service import ItemBookMasterService
from app.models.documents.item_book_master_document import (
    ItemBookMasterDocument,
    ItemBookCategory,
    ItemBookTab,
    ItemBookButton,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    """Create a service with mocked repositories."""
    book_repo = AsyncMock()
    common_repo = AsyncMock()
    store_repo = AsyncMock()
    svc = ItemBookMasterService(
        item_book_master_repo=book_repo,
        item_common_master_repo=common_repo,
        item_store_master_repo=store_repo,
    )
    return svc, book_repo, common_repo, store_repo


def _make_item_book(
    item_book_id="BK-001",
    categories=None,
):
    """Create a minimal ItemBookMasterDocument for testing."""
    doc = ItemBookMasterDocument()
    doc.item_book_id = item_book_id
    doc.title = "Test Book"
    doc.categories = categories or []
    return doc


def _make_category(category_number=1, tabs=None):
    return ItemBookCategory(
        category_number=category_number,
        title=f"Category {category_number}",
        color="#000",
        tabs=tabs or [],
    )


def _make_tab(tab_number=1, buttons=None):
    return ItemBookTab(
        tab_number=tab_number,
        title=f"Tab {tab_number}",
        color="#111",
        buttons=buttons or [],
    )


def _make_button(pos_x=0, pos_y=0, item_code="ITEM-01"):
    return ItemBookButton(
        pos_x=pos_x,
        pos_y=pos_y,
        size="Single",
        item_code=item_code,
        color_text="#FFF",
    )


# ---------------------------------------------------------------------------
# create_item_book_async
# ---------------------------------------------------------------------------

class TestCreateItemBook:
    @pytest.mark.asyncio
    async def test_create_success(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None  # ID not taken
        created_doc = _make_item_book()
        book_repo.create_item_book_async.return_value = created_doc

        result = await svc.create_item_book_async("My Book", [])
        assert result == created_doc
        book_repo.create_item_book_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_generates_unique_id(self):
        """If first ID is taken, it increments sequence."""
        svc, book_repo, _, _ = _make_service()
        existing = _make_item_book()
        book_repo.get_item_book_async.side_effect = [existing, None]
        book_repo.create_item_book_async.return_value = _make_item_book()

        await svc.create_item_book_async("Book", [])
        # Should have called get_item_book_async twice (first exists, second does not)
        assert book_repo.get_item_book_async.await_count == 2


# ---------------------------------------------------------------------------
# get_item_book_by_id_async
# ---------------------------------------------------------------------------

class TestGetItemBookById:
    @pytest.mark.asyncio
    async def test_get_success(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book()
        book_repo.get_item_book_async.return_value = doc

        result = await svc.get_item_book_by_id_async("BK-001")
        assert result == doc

    @pytest.mark.asyncio
    async def test_get_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.get_item_book_by_id_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# get_item_book_detail_by_id_async
# ---------------------------------------------------------------------------

class TestGetItemBookDetail:
    @pytest.mark.asyncio
    async def test_detail_enriches_buttons(self):
        svc, book_repo, common_repo, store_repo = _make_service()

        btn = _make_button(item_code="ITEM-01")
        tab = _make_tab(buttons=[btn])
        cat = _make_category(tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        common_item = MagicMock()
        common_item.description = "Test Item"
        common_item.unit_price = 100.0
        common_repo.get_item_by_code_async.return_value = common_item

        store_item = MagicMock()
        store_item.store_price = 120.0
        store_repo.get_item_store_by_code.return_value = store_item

        result = await svc.get_item_book_detail_by_id_async("BK-001")
        button = result.categories[0].tabs[0].buttons[0]
        assert button.description == "Test Item"
        assert button.unit_price == 120.0  # overridden by store price

    @pytest.mark.asyncio
    async def test_detail_item_not_found_has_no_price_or_name(self):
        """A button whose item is not in the item master gets null for both,
        not the string "not found", and not a price that was there before."""
        svc, book_repo, common_repo, store_repo = _make_service()

        btn = _make_button(item_code="MISSING")
        # Assignment is not validated, so this stands in for a value already present.
        btn.unit_price = 5.0
        btn.description = "stale"
        tab = _make_tab(buttons=[btn])
        cat = _make_category(tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc
        common_repo.get_item_by_code_async.return_value = None

        result = await svc.get_item_book_detail_by_id_async("BK-001")
        button = result.categories[0].tabs[0].buttons[0]
        assert button.description is None
        assert button.unit_price is None

    @pytest.mark.asyncio
    async def test_detail_no_store_price_uses_common(self):
        svc, book_repo, common_repo, store_repo = _make_service()

        btn = _make_button()
        tab = _make_tab(buttons=[btn])
        cat = _make_category(tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        common_item = MagicMock()
        common_item.description = "Item"
        common_item.unit_price = 100.0
        common_repo.get_item_by_code_async.return_value = common_item
        store_repo.get_item_store_by_code.return_value = None

        result = await svc.get_item_book_detail_by_id_async("BK-001")
        assert result.categories[0].tabs[0].buttons[0].unit_price == 100.0

    @pytest.mark.asyncio
    async def test_detail_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.get_item_book_detail_by_id_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# get_item_book_all_async / get_item_book_all_paginated_async
# ---------------------------------------------------------------------------

class TestGetAllItemBooks:
    @pytest.mark.asyncio
    async def test_get_all(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_by_filter_async.return_value = []

        result = await svc.get_item_book_all_async(limit=10, page=1, sort=[])
        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_paginated(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_by_filter_async.return_value = [_make_item_book()]
        book_repo.get_item_book_count_by_filter_async.return_value = 1

        items, total = await svc.get_item_book_all_paginated_async(
            limit=10, page=1, sort=[]
        )
        assert len(items) == 1
        assert total == 1


# ---------------------------------------------------------------------------
# update_item_book_async
# ---------------------------------------------------------------------------

class TestUpdateItemBook:
    @pytest.mark.asyncio
    async def test_update_success(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book()
        book_repo.get_item_book_async.return_value = doc
        updated = _make_item_book()
        book_repo.update_item_book_async.return_value = updated

        result = await svc.update_item_book_async("BK-001", {"title": "New"})
        assert result == updated

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.update_item_book_async("NONEXISTENT", {})


# ---------------------------------------------------------------------------
# delete_item_book_async
# ---------------------------------------------------------------------------

class TestDeleteItemBook:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = _make_item_book()

        await svc.delete_item_book_async("BK-001")
        book_repo.delete_item_book_async.assert_awaited_once_with("BK-001")

    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.delete_item_book_async("NONEXISTENT")


# ---------------------------------------------------------------------------
# add_category_to_item_book_async
# ---------------------------------------------------------------------------

class TestAddCategory:
    @pytest.mark.asyncio
    async def test_add_category_success(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book(categories=[])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.add_category_to_item_book_async(
            "BK-001", {"category_number": 1, "title": "New Cat", "color": "#F00", "tabs": []}
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.add_category_async.assert_awaited_once()
        item_book_id, category = book_repo.add_category_async.await_args.args
        assert item_book_id == "BK-001"
        assert (category["category_number"], category["title"]) == (1, "New Cat")
        assert result is doc

    @pytest.mark.asyncio
    async def test_add_category_duplicate_raises(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1)
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentAlreadyExistsException):
            await svc.add_category_to_item_book_async(
                "BK-001", {"category_number": 1, "title": "Dup", "color": "#000", "tabs": []}
            )

    @pytest.mark.asyncio
    async def test_add_category_book_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.add_category_to_item_book_async("NONEXISTENT", {"category_number": 1})


# ---------------------------------------------------------------------------
# update_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestUpdateCategory:
    @pytest.mark.asyncio
    async def test_update_category_success(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1)
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.update_category_in_item_book_async(
            "BK-001", 1, {"category_number": 1, "title": "Updated"}
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        # Fields the request does not give (color, tabs) are not written back.
        book_repo.set_category_fields_async.assert_awaited_once_with(
            "BK-001", 1, {"category_number": 1, "title": "Updated"}
        )
        assert result is doc

    @pytest.mark.asyncio
    async def test_update_category_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book(categories=[])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.update_category_in_item_book_async("BK-001", 99, {})

    @pytest.mark.asyncio
    async def test_update_category_move_to_existing_number_raises(self):
        svc, book_repo, _, _ = _make_service()
        cat1 = _make_category(category_number=1)
        cat2 = _make_category(category_number=2)
        doc = _make_item_book(categories=[cat1, cat2])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(InvalidRequestDataException):
            await svc.update_category_in_item_book_async(
                "BK-001", 1, {"category_number": 2}
            )


# ---------------------------------------------------------------------------
# delete_category_from_item_book_async
# ---------------------------------------------------------------------------

class TestDeleteCategory:
    @pytest.mark.asyncio
    async def test_delete_category_success(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1)
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.delete_category_from_item_book_async("BK-001", 1)

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.delete_category_async.assert_awaited_once_with("BK-001", 1)
        assert result is doc

    @pytest.mark.asyncio
    async def test_delete_category_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book(categories=[])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.delete_category_from_item_book_async("BK-001", 99)


# ---------------------------------------------------------------------------
# add_tab_to_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestAddTab:
    @pytest.mark.asyncio
    async def test_add_tab_success(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1, tabs=[])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.add_tab_to_category_in_item_book_async(
            "BK-001", 1, {"tab_number": 1, "title": "Tab", "color": "#000", "buttons": []}
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.add_tab_async.assert_awaited_once()
        item_book_id, category_number, tab = book_repo.add_tab_async.await_args.args
        assert (item_book_id, category_number) == ("BK-001", 1)
        assert (tab["tab_number"], tab["title"]) == (1, "Tab")
        assert result is doc

    @pytest.mark.asyncio
    async def test_add_tab_duplicate_raises(self):
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1)
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentAlreadyExistsException):
            await svc.add_tab_to_category_in_item_book_async(
                "BK-001", 1, {"tab_number": 1, "title": "Dup"}
            )

    @pytest.mark.asyncio
    async def test_add_tab_category_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book(categories=[])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.add_tab_to_category_in_item_book_async(
                "BK-001", 99, {"tab_number": 1}
            )

    @pytest.mark.asyncio
    async def test_add_tab_book_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.add_tab_to_category_in_item_book_async("NONEXISTENT", 1, {})


# ---------------------------------------------------------------------------
# update_tab_in_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestUpdateTab:
    @pytest.mark.asyncio
    async def test_update_tab_success(self):
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1)
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.update_tab_in_category_in_item_book_async(
            "BK-001", 1, 1, {"tab_number": 1, "title": "Updated Tab"}
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        # Fields the request does not give (color, buttons) are not written back.
        book_repo.set_tab_fields_async.assert_awaited_once_with(
            "BK-001", 1, 1, {"tab_number": 1, "title": "Updated Tab"}
        )
        assert result is doc

    @pytest.mark.asyncio
    async def test_update_tab_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1, tabs=[])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.update_tab_in_category_in_item_book_async("BK-001", 1, 99, {})

    @pytest.mark.asyncio
    async def test_update_tab_move_to_existing_raises(self):
        svc, book_repo, _, _ = _make_service()
        tab1 = _make_tab(tab_number=1)
        tab2 = _make_tab(tab_number=2)
        cat = _make_category(category_number=1, tabs=[tab1, tab2])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(InvalidRequestDataException):
            await svc.update_tab_in_category_in_item_book_async(
                "BK-001", 1, 1, {"tab_number": 2}
            )


# ---------------------------------------------------------------------------
# delete_tab_from_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestDeleteTab:
    @pytest.mark.asyncio
    async def test_delete_tab_success(self):
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1)
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.delete_tab_from_category_in_item_book_async("BK-001", 1, 1)

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.delete_tab_async.assert_awaited_once_with("BK-001", 1, 1)
        assert result is doc

    @pytest.mark.asyncio
    async def test_delete_tab_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1, tabs=[])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.delete_tab_from_category_in_item_book_async("BK-001", 1, 99)


# ---------------------------------------------------------------------------
# add_button_to_tab_in_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestAddButton:
    @pytest.mark.asyncio
    async def test_add_button_success(self):
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1, buttons=[])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.add_button_to_tab_in_category_in_item_book_async(
            "BK-001", 1, 1, {"pos_x": 0, "pos_y": 0, "item_code": "ITEM-01", "size": "Single"}
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.add_button_async.assert_awaited_once()
        item_book_id, category_number, tab_number, button = book_repo.add_button_async.await_args.args
        assert (item_book_id, category_number, tab_number) == ("BK-001", 1, 1)
        assert (button["pos_x"], button["pos_y"], button["item_code"]) == (0, 0, "ITEM-01")
        assert result is doc

    @pytest.mark.asyncio
    async def test_add_button_does_not_store_display_values(self):
        """Price and name are display-only (#262); the atomic $push must not store them either."""
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1, buttons=[])
        cat = _make_category(category_number=1, tabs=[tab])
        book_repo.get_item_book_async.return_value = _make_item_book(categories=[cat])

        await svc.add_button_to_tab_in_category_in_item_book_async(
            "BK-001", 1, 1, {"pos_x": 0, "pos_y": 0, "item_code": "ITEM-01", "unit_price": 9999, "description": "x"}
        )

        button = book_repo.add_button_async.await_args.args[3]
        assert "unit_price" not in button
        assert "description" not in button

    @pytest.mark.asyncio
    async def test_add_button_duplicate_position_raises(self):
        svc, book_repo, _, _ = _make_service()
        btn = _make_button(pos_x=0, pos_y=0)
        tab = _make_tab(tab_number=1, buttons=[btn])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentAlreadyExistsException):
            await svc.add_button_to_tab_in_category_in_item_book_async(
                "BK-001", 1, 1, {"pos_x": 0, "pos_y": 0, "item_code": "X"}
            )

    @pytest.mark.asyncio
    async def test_add_button_tab_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        cat = _make_category(category_number=1, tabs=[])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.add_button_to_tab_in_category_in_item_book_async(
                "BK-001", 1, 99, {"pos_x": 0, "pos_y": 0}
            )


# ---------------------------------------------------------------------------
# update_button_in_tab_in_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestUpdateButton:
    @pytest.mark.asyncio
    async def test_update_button_success(self):
        svc, book_repo, _, _ = _make_service()
        btn = _make_button(pos_x=0, pos_y=0)
        tab = _make_tab(tab_number=1, buttons=[btn])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.update_button_in_tab_in_category_in_item_book_async(
            "BK-001", 1, 1, 0, 0, {"pos_x": 0, "pos_y": 0, "item_code": "ITEM-02"}
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.set_button_fields_async.assert_awaited_once_with(
            "BK-001", 1, 1, 0, 0, {"pos_x": 0, "pos_y": 0, "item_code": "ITEM-02"}
        )
        assert result is doc

    @pytest.mark.asyncio
    @pytest.mark.parametrize("start, target", [((2, 3), (0, 3)), ((2, 3), (2, 0)), ((2, 3), (0, 0))])
    async def test_update_button_moves_to_coordinate_zero(self, start, target):
        """0 is a coordinate, not "not given": the button lands in the first column or row."""
        svc, book_repo, _, _ = _make_service()
        btn = _make_button(pos_x=start[0], pos_y=start[1])
        tab = _make_tab(tab_number=1, buttons=[btn])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        await svc.update_button_in_tab_in_category_in_item_book_async(
            "BK-001", 1, 1, start[0], start[1], {"pos_x": target[0], "pos_y": target[1], "item_code": "ITEM-01"}
        )

        fields = book_repo.set_button_fields_async.await_args.args[5]
        assert (fields["pos_x"], fields["pos_y"]) == target

    @pytest.mark.asyncio
    async def test_update_button_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1, buttons=[])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.update_button_in_tab_in_category_in_item_book_async(
                "BK-001", 1, 1, 5, 5, {}
            )

    @pytest.mark.asyncio
    async def test_update_button_move_to_existing_position_raises(self):
        svc, book_repo, _, _ = _make_service()
        btn1 = _make_button(pos_x=0, pos_y=0)
        btn2 = _make_button(pos_x=1, pos_y=1)
        tab = _make_tab(tab_number=1, buttons=[btn1, btn2])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(InvalidRequestDataException):
            await svc.update_button_in_tab_in_category_in_item_book_async(
                "BK-001", 1, 1, 0, 0, {"pos_x": 1, "pos_y": 1}
            )


# ---------------------------------------------------------------------------
# delete_button_from_tab_in_category_in_item_book_async
# ---------------------------------------------------------------------------

class TestDeleteButton:
    @pytest.mark.asyncio
    async def test_delete_button_success(self):
        svc, book_repo, _, _ = _make_service()
        btn = _make_button(pos_x=0, pos_y=0)
        tab = _make_tab(tab_number=1, buttons=[btn])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.delete_button_from_tab_in_category_in_item_book_async(
            "BK-001", 1, 1, 0, 0
        )

        # The write itself is an atomic repository operation, so a unit test checks
        # which write was asked for; the stored result is pinned by the integration
        # tests against a real MongoDB (test_item_book_concurrent_writes.py).
        book_repo.delete_button_async.assert_awaited_once_with("BK-001", 1, 1, 0, 0)
        assert result is doc

    @pytest.mark.asyncio
    async def test_delete_button_names_both_coordinates(self):
        """Issue #137: deleting (1, 1) on a 3x3 grid removes that button only.
        The old AND-of-not-equal condition also wiped (0, 1), (2, 1), (1, 0)
        and (1, 2). The service names the (pos_x, pos_y) pair; the repository's
        $pull on that pair is checked against a real MongoDB in the integration tier."""
        svc, book_repo, _, _ = _make_service()
        grid = [_make_button(pos_x=x, pos_y=y, item_code=f"ITEM-{x}{y}") for x in range(3) for y in range(3)]
        tab = _make_tab(tab_number=1, buttons=grid)
        cat = _make_category(category_number=1, tabs=[tab])
        book_repo.get_item_book_async.return_value = _make_item_book(categories=[cat])

        await svc.delete_button_from_tab_in_category_in_item_book_async("BK-001", 1, 1, 1, 1)

        book_repo.delete_button_async.assert_awaited_once_with("BK-001", 1, 1, 1, 1)

    @pytest.mark.asyncio
    async def test_delete_button_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        tab = _make_tab(tab_number=1, buttons=[])
        cat = _make_category(category_number=1, tabs=[tab])
        doc = _make_item_book(categories=[cat])
        book_repo.get_item_book_async.return_value = doc

        with pytest.raises(DocumentNotFoundException):
            await svc.delete_button_from_tab_in_category_in_item_book_async(
                "BK-001", 1, 1, 5, 5
            )

    @pytest.mark.asyncio
    async def test_delete_button_book_not_found_raises(self):
        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await svc.delete_button_from_tab_in_category_in_item_book_async(
                "NONEXISTENT", 1, 1, 0, 0
            )


# ---------------------------------------------------------------------------
# Re-reading when a concurrent write broke the precondition
# ---------------------------------------------------------------------------

class TestNestedWriteRetry:
    @pytest.mark.asyncio
    async def test_a_lost_race_is_re_validated_against_a_fresh_read(self):
        """The atomic add found the position taken; the re-read turns that into the duplicate error."""
        svc, book_repo, _, _ = _make_service()
        empty_tab = _make_tab(tab_number=1, buttons=[])
        taken_tab = _make_tab(tab_number=1, buttons=[_make_button(pos_x=0, pos_y=0)])
        book_repo.get_item_book_async.side_effect = [
            _make_item_book(categories=[_make_category(category_number=1, tabs=[empty_tab])]),
            _make_item_book(categories=[_make_category(category_number=1, tabs=[taken_tab])]),
        ]
        book_repo.add_button_async.return_value = False

        with pytest.raises(DocumentAlreadyExistsException):
            await svc.add_button_to_tab_in_category_in_item_book_async(
                "BK-001", 1, 1, {"pos_x": 0, "pos_y": 0, "item_code": "X"}
            )
        book_repo.add_button_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_write_that_never_lands_fails_after_the_attempt_limit(self):
        from app.services.item_book_master_service import NESTED_WRITE_ATTEMPTS

        svc, book_repo, _, _ = _make_service()
        book_repo.get_item_book_async.return_value = _make_item_book(categories=[])
        book_repo.add_category_async.return_value = False

        with pytest.raises(Exception, match="Failed to update item book"):
            await svc.add_category_to_item_book_async("BK-001", {"category_number": 1, "tabs": []})
        assert book_repo.add_category_async.await_count == NESTED_WRITE_ATTEMPTS

    @pytest.mark.asyncio
    async def test_an_update_with_nothing_to_write_does_not_write(self):
        svc, book_repo, _, _ = _make_service()
        doc = _make_item_book(categories=[_make_category(category_number=1)])
        book_repo.get_item_book_async.return_value = doc

        result = await svc.update_category_in_item_book_async("BK-001", 1, {})

        book_repo.set_category_fields_async.assert_not_awaited()
        assert result is doc

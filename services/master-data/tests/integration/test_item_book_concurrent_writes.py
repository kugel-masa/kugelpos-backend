# Copyright 2026 masa@kugel
"""Concurrent nested writes to an item book do not overwrite each other.

Adding, updating and deleting a category, tab or button used to read the whole
book, change it in memory and replace it. Whatever another request wrote between
the read and the replace was lost, and the losing request still answered 201 /
200. Six buttons posted in parallel to one tab all returned 201 and left one to
three behind (stpos fork, 69bd0bcaf).

Calling the endpoints one after another passes on the old code too, so every test
here runs its writes concurrently with asyncio.gather. Each request gets its own
service, as each HTTP request builds its own through dependency injection; one
shared instance could serialise them by accident.
"""

import asyncio
import os

import pytest
import pytest_asyncio

from kugel_common.exceptions import DocumentAlreadyExistsException

from app.config.settings import settings
from app.models.repositories.item_book_master_repository import ItemBookMasterRepository
from app.models.repositories.item_common_master_repository import ItemCommonMasterRepository
from app.services.item_book_master_service import ItemBookMasterService

pytestmark = pytest.mark.asyncio

# A tenant of its own, dropped afterwards, so no other test's data is touched.
_TENANT_ID = "IBCW1"
_DB_NAME = f"{settings.DB_NAME_PREFIX}_{_TENANT_ID}"


async def _db():
    from kugel_common.database import database as db_helper

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    return await db_helper.get_db_async(_DB_NAME)


async def _service() -> ItemBookMasterService:
    """The service one request would build."""
    db = await _db()
    return ItemBookMasterService(
        item_book_master_repo=ItemBookMasterRepository(db, _TENANT_ID),
        item_common_master_repo=ItemCommonMasterRepository(db, _TENANT_ID),
        item_store_master_repo=None,
    )


@pytest_asyncio.fixture
async def tenant_db():
    from kugel_common.database import database as db_helper
    from app.database import database_setup

    db_helper.MONGODB_URI = os.environ.get("MONGODB_URI")
    client = await db_helper.get_client_async()
    await client.drop_database(_DB_NAME)
    try:
        await database_setup.create_collections(_TENANT_ID)
        yield
    finally:
        await client.drop_database(_DB_NAME)


def _category(number: int, tabs: list | None = None) -> dict:
    return {"category_number": number, "title": f"category {number}", "color": "#ffffff", "tabs": tabs or []}


def _tab(number: int, buttons: list | None = None) -> dict:
    return {"tab_number": number, "title": f"tab {number}", "color": "#eeeeee", "buttons": buttons or []}


def _button(pos_x: int, pos_y: int) -> dict:
    return {
        "pos_x": pos_x,
        "pos_y": pos_y,
        "size": "Single",
        "image_url": "",
        "color_text": "#000000",
        "item_code": f"ITEM{pos_x}{pos_y}",
    }


async def _create_book(categories: list[dict] | None = None) -> str:
    service = await _service()
    item_book = await service.create_item_book_async(title="concurrency probe", categories=categories or [])
    return item_book.item_book_id


async def _read_book(item_book_id: str):
    service = await _service()
    return await service.get_item_book_by_id_async(item_book_id)


def _find_category(item_book, category_number: int):
    return next((c for c in item_book.categories if c.category_number == category_number), None)


def _find_tab(item_book, category_number: int, tab_number: int):
    category = _find_category(item_book, category_number)
    return next((t for t in category.tabs if t.tab_number == tab_number), None)


async def _run_concurrently(make_coroutine, arguments: list):
    services = [await _service() for _ in arguments]
    return await asyncio.gather(*[make_coroutine(service, argument) for service, argument in zip(services, arguments)])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def test_concurrent_category_add_keeps_every_category(tenant_db):
    item_book_id = await _create_book()
    numbers = [1, 2, 3, 4, 5, 6]

    await _run_concurrently(
        lambda service, number: service.add_category_to_item_book_async(item_book_id, _category(number)),
        numbers,
    )

    stored = sorted(c.category_number for c in (await _read_book(item_book_id)).categories)
    assert stored == numbers


async def test_concurrent_category_update_keeps_every_change(tenant_db):
    item_book_id = await _create_book([_category(n) for n in (1, 2, 3, 4)])
    targets = [1, 3]

    await _run_concurrently(
        lambda service, number: service.update_category_in_item_book_async(
            item_book_id, number, {"category_number": number, "title": f"renamed {number}"}
        ),
        targets,
    )

    item_book = await _read_book(item_book_id)
    assert {n: _find_category(item_book, n).title for n in targets} == {n: f"renamed {n}" for n in targets}


async def test_concurrent_category_delete_removes_only_the_targets(tenant_db):
    item_book_id = await _create_book([_category(n) for n in (1, 2, 3, 4)])

    await _run_concurrently(
        lambda service, number: service.delete_category_from_item_book_async(item_book_id, number),
        [1, 3],
    )

    remaining = sorted(c.category_number for c in (await _read_book(item_book_id)).categories)
    assert remaining == [2, 4]


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


async def test_concurrent_tab_add_keeps_every_tab(tenant_db):
    item_book_id = await _create_book([_category(1)])
    numbers = [1, 2, 3, 4, 5, 6]

    await _run_concurrently(
        lambda service, number: service.add_tab_to_category_in_item_book_async(item_book_id, 1, _tab(number)),
        numbers,
    )

    stored = sorted(t.tab_number for t in _find_category(await _read_book(item_book_id), 1).tabs)
    assert stored == numbers


async def test_concurrent_tab_update_keeps_every_change(tenant_db):
    item_book_id = await _create_book([_category(1, [_tab(n) for n in (1, 2, 3, 4)])])
    targets = [1, 3]

    await _run_concurrently(
        lambda service, number: service.update_tab_in_category_in_item_book_async(
            item_book_id, 1, number, {"tab_number": number, "title": f"renamed {number}"}
        ),
        targets,
    )

    item_book = await _read_book(item_book_id)
    assert {n: _find_tab(item_book, 1, n).title for n in targets} == {n: f"renamed {n}" for n in targets}


async def test_concurrent_tab_delete_removes_only_the_targets(tenant_db):
    item_book_id = await _create_book([_category(1, [_tab(n) for n in (1, 2, 3, 4)])])

    await _run_concurrently(
        lambda service, number: service.delete_tab_from_category_in_item_book_async(item_book_id, 1, number),
        [1, 3],
    )

    remaining = sorted(t.tab_number for t in _find_category(await _read_book(item_book_id), 1).tabs)
    assert remaining == [2, 4]


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------


async def test_concurrent_button_add_keeps_every_button(tenant_db):
    """The reported case: six buttons at different positions added to one tab at once."""
    item_book_id = await _create_book([_category(1, [_tab(1)])])
    positions = [(10, y) for y in (1, 2, 3, 4, 5, 6)]

    await _run_concurrently(
        lambda service, position: service.add_button_to_tab_in_category_in_item_book_async(
            item_book_id, 1, 1, _button(*position)
        ),
        positions,
    )

    stored = sorted((b.pos_x, b.pos_y) for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons)
    assert stored == positions


async def test_concurrent_button_update_keeps_every_change(tenant_db):
    item_book_id = await _create_book([_category(1, [_tab(1, [_button(10, y) for y in (1, 2, 3, 4)])])])
    targets = [(10, 1), (10, 3)]

    await _run_concurrently(
        lambda service, position: service.update_button_in_tab_in_category_in_item_book_async(
            item_book_id,
            1,
            1,
            position[0],
            position[1],
            {"pos_x": position[0], "pos_y": position[1], "color_text": f"#00000{position[1]}"},
        ),
        targets,
    )

    buttons = {(b.pos_x, b.pos_y): b.color_text for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons}
    assert {p: buttons[p] for p in targets} == {p: f"#00000{p[1]}" for p in targets}


async def test_concurrent_button_delete_removes_only_the_targets(tenant_db):
    item_book_id = await _create_book([_category(1, [_tab(1, [_button(10, y) for y in (1, 2, 3, 4)])])])

    await _run_concurrently(
        lambda service, position: service.delete_button_from_tab_in_category_in_item_book_async(
            item_book_id, 1, 1, position[0], position[1]
        ),
        [(10, 1), (10, 3)],
    )

    remaining = sorted((b.pos_x, b.pos_y) for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons)
    assert remaining == [(10, 2), (10, 4)]


async def test_concurrent_button_add_at_the_same_position_stores_one(tenant_db):
    """Two requests claiming one position: one button is stored, the other request is refused.

    This is the re-read path. The atomic update writes nothing once the position is
    taken, so the service reads again and its duplicate check refuses the request.
    Neither two buttons at one position nor a lost request answering success is allowed.
    """
    item_book_id = await _create_book([_category(1, [_tab(1)])])
    services = [await _service() for _ in range(2)]

    outcomes = await asyncio.gather(
        *[
            service.add_button_to_tab_in_category_in_item_book_async(item_book_id, 1, 1, _button(10, 1))
            for service in services
        ],
        return_exceptions=True,
    )

    stored = sorted((b.pos_x, b.pos_y) for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons)
    assert stored == [(10, 1)]
    rejected = [outcome for outcome in outcomes if isinstance(outcome, DocumentAlreadyExistsException)]
    assert len(rejected) == 1, outcomes


# ---------------------------------------------------------------------------
# Two fields of one element, updated at once
# ---------------------------------------------------------------------------


async def test_concurrent_update_of_two_fields_on_the_same_category_keeps_both(tenant_db):
    item_book_id = await _create_book([_category(1)])

    await _run_concurrently(
        lambda service, update: service.update_category_in_item_book_async(item_book_id, 1, update),
        [{"title": "renamed"}, {"color": "#123456"}],
    )

    category = _find_category(await _read_book(item_book_id), 1)
    assert (category.title, category.color) == ("renamed", "#123456")


async def test_concurrent_update_of_two_fields_on_the_same_tab_keeps_both(tenant_db):
    item_book_id = await _create_book([_category(1, [_tab(1)])])

    await _run_concurrently(
        lambda service, update: service.update_tab_in_category_in_item_book_async(item_book_id, 1, 1, update),
        [{"title": "renamed"}, {"color": "#123456"}],
    )

    tab = _find_tab(await _read_book(item_book_id), 1, 1)
    assert (tab.title, tab.color) == ("renamed", "#123456")


async def test_concurrent_update_of_two_fields_on_the_same_button_keeps_both(tenant_db):
    item_book_id = await _create_book([_category(1, [_tab(1, [_button(10, 1)])])])

    await _run_concurrently(
        lambda service, update: service.update_button_in_tab_in_category_in_item_book_async(
            item_book_id, 1, 1, 10, 1, update
        ),
        [
            {"pos_x": 10, "pos_y": 1, "color_text": "#123456"},
            {"pos_x": 10, "pos_y": 1, "item_code": "ITEM999"},
        ],
    )

    button = _find_tab(await _read_book(item_book_id), 1, 1).buttons[0]
    assert (button.color_text, button.item_code) == ("#123456", "ITEM999")


# ---------------------------------------------------------------------------
# What the earlier item book fixes guarantee, against the atomic writes
# ---------------------------------------------------------------------------


async def test_deleting_a_button_keeps_its_row_and_column(tenant_db):
    """#137: the $pull names the (pos_x, pos_y) pair, not each axis on its own."""
    grid = [_button(x, y) for x in range(3) for y in range(3)]
    item_book_id = await _create_book([_category(1, [_tab(1, grid)])])

    service = await _service()
    await service.delete_button_from_tab_in_category_in_item_book_async(item_book_id, 1, 1, 1, 1)

    remaining = {(b.pos_x, b.pos_y) for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons}
    assert remaining == {(x, y) for x in range(3) for y in range(3)} - {(1, 1)}


async def test_a_button_moves_to_coordinate_zero(tenant_db):
    """#264: 0 is a position, not "not given"."""
    item_book_id = await _create_book([_category(1, [_tab(1, [_button(2, 3)])])])

    service = await _service()
    await service.update_button_in_tab_in_category_in_item_book_async(
        item_book_id, 1, 1, 2, 3, {"pos_x": 0, "pos_y": 0}
    )

    stored = [(b.pos_x, b.pos_y) for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons]
    assert stored == [(0, 0)]


async def test_display_values_are_not_stored(tenant_db):
    """#262: price and name are display-only; the atomic $push does not store them."""
    item_book_id = await _create_book([_category(1, [_tab(1)])])

    service = await _service()
    await service.add_button_to_tab_in_category_in_item_book_async(
        item_book_id, 1, 1, {**_button(0, 0), "unit_price": 9999, "description": "shadow"}
    )

    raw = await (await _db())[settings.DB_COLLECTION_NAME_ITEM_BOOK_MASTER].find_one({"item_book_id": item_book_id})
    button = raw["categories"][0]["tabs"][0]["buttons"][0]
    assert "unit_price" not in button
    assert "description" not in button


@pytest.mark.parametrize("null_list", ["categories", "tabs", "buttons"])
async def test_a_stored_null_list_still_takes_a_new_element(tenant_db, null_list):
    """#264: a book written before null lists were refused can hold one, and $push
    into a null field fails. The repository empties such a list first."""
    item_book_id = await _create_book([_category(1, [_tab(1)])])
    path = {"categories": "categories", "tabs": "categories.0.tabs", "buttons": "categories.0.tabs.0.buttons"}[
        null_list
    ]
    collection = (await _db())[settings.DB_COLLECTION_NAME_ITEM_BOOK_MASTER]
    await collection.update_one({"item_book_id": item_book_id}, {"$set": {path: None}})

    service = await _service()
    if null_list == "categories":
        await service.add_category_to_item_book_async(item_book_id, _category(2))
        stored = [c.category_number for c in (await _read_book(item_book_id)).categories]
        assert stored == [2]
    elif null_list == "tabs":
        await service.add_tab_to_category_in_item_book_async(item_book_id, 1, _tab(2))
        stored = [t.tab_number for t in _find_category(await _read_book(item_book_id), 1).tabs]
        assert stored == [2]
    else:
        await service.add_button_to_tab_in_category_in_item_book_async(item_book_id, 1, 1, _button(0, 0))
        stored = [(b.pos_x, b.pos_y) for b in _find_tab(await _read_book(item_book_id), 1, 1).buttons]
        assert stored == [(0, 0)]

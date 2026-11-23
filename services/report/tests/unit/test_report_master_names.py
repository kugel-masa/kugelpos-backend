"""Category names are read from every page, deleted ones included (issue #326)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import CategoryMasterDataNotFoundException
from app.models.repositories.category_master_web_repository import CategoryMasterWebRepository
from app.utils.master_data_pages import MAX_MASTER_DATA_PAGES, has_next_page
from kugel_common.utils.http_client_helper import HttpClientError


@pytest.mark.parametrize(
    "metadata, page, received, expected",
    [
        ({"total": 250, "page": 2, "limit": 100}, 2, 100, True),
        ({"total": 200, "page": 2, "limit": 100}, 2, 100, False),
        ({"has_next": False}, 1, 100, False),
        ({"totalPages": 3}, 2, 100, True),
        (None, 1, 100, True),
        (None, 1, 99, False),
        ({"total": 999}, 3, 0, False),
    ],
    ids=["total-more", "total-done", "has-next", "total-pages", "full-page", "short-page", "empty-page"],
)
def test_has_next_page(metadata, page, received, expected):
    assert has_next_page(metadata, page, received) is expected


def _page(categories, total):
    return {"success": True, "data": categories, "metadata": {"total": total}}


def _patched(client):
    @asynccontextmanager
    async def fake_client(name, **kwargs):
        yield client

    return patch(
        "app.models.repositories.category_master_web_repository.get_service_client", fake_client
    ), patch("app.models.repositories.category_master_web_repository.create_service_token", return_value="token")


@pytest.mark.asyncio
async def test_every_page_is_read_and_deleted_categories_are_asked_for():
    first = [{"categoryCode": f"C{i:03d}", "description": f"Cat {i}"} for i in range(100)]
    second = [{"categoryCode": "LATE", "description": "Past the first page"}, {"categoryCode": "BARE"}]
    client = AsyncMock()
    client.get = AsyncMock(side_effect=[_page(first, 102), _page(second, 102)])
    a, b = _patched(client)
    with a, b:
        names = await CategoryMasterWebRepository("T1", "http://md").get_categories()

    assert len(names) == 102
    assert names["LATE"] == "Past the first page"
    assert names["BARE"] == "BARE"
    params = [c.kwargs["params"] for c in client.get.await_args_list]
    assert [p["page"] for p in params] == [1, 2]
    assert all(p["include_deleted"] == "true" for p in params)


@pytest.mark.asyncio
async def test_no_categories_is_an_empty_map():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_page([], 0))
    a, b = _patched(client)
    with a, b:
        assert await CategoryMasterWebRepository("T1", "http://md").get_categories() == {}


@pytest.mark.asyncio
async def test_a_failure_on_a_later_page_fails_the_whole_read():
    client = AsyncMock()
    client.get = AsyncMock(
        side_effect=[_page([{"categoryCode": "C1", "description": "x"}] * 100, 150), RuntimeError("gone")]
    )
    a, b = _patched(client)
    with a, b, pytest.raises(CategoryMasterDataNotFoundException):
        await CategoryMasterWebRepository("T1", "http://md").get_categories()


def test_reading_stops_at_the_page_cap():
    assert has_next_page({"has_next": True}, MAX_MASTER_DATA_PAGES - 1, 100) is True
    assert has_next_page({"has_next": True}, MAX_MASTER_DATA_PAGES, 100) is False


@pytest.mark.asyncio
async def test_a_connection_failure_is_a_category_read_failure():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=HttpClientError("unreachable"))
    a, b = _patched(client)
    with a, b, pytest.raises(CategoryMasterDataNotFoundException):
        await CategoryMasterWebRepository("T1", "http://md").get_categories()

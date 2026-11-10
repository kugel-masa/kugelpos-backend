# Copyright 2026 masa@kugel
"""A query in the URL survives a request made without params.

httpx replaces the URL's query with ``params`` whenever ``params`` is given.
``request()`` used to default a missing ``params`` to an empty dict and pass it,
so a query carried in the URL was dropped. (``get()`` and ``post()`` pass
``params=None`` through, which httpx leaves alone.)
"""
import httpx
import pytest
import respx

from kugel_common.utils.http_client_helper import HttpClientHelper


@pytest.mark.asyncio
@respx.mock
async def test_a_query_in_the_endpoint_is_kept():
    route = respx.get("http://api.example.com/files/a").mock(return_value=httpx.Response(200, json={}))

    async with HttpClientHelper(base_url="http://api.example.com") as helper:
        await helper.request("GET", "/files/a?sv=2024&sig=abc")

    assert route.called
    assert dict(route.calls.last.request.url.params) == {"sv": "2024", "sig": "abc"}


@pytest.mark.asyncio
@respx.mock
async def test_params_are_still_sent():
    route = respx.get("http://api.example.com/items").mock(return_value=httpx.Response(200, json={}))

    async with HttpClientHelper(base_url="http://api.example.com") as helper:
        await helper.get("/items", params={"page": 2})

    assert dict(route.calls.last.request.url.params) == {"page": "2"}

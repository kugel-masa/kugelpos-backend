# Copyright 2026 masa@kugel
"""The API key of a terminal these tests did not just create.

A terminal's key is stored as a digest and cannot be read back (issue #136);
it is issued anew with POST /terminals/{terminal_id}/api-key, which invalidates
the previous one. Several modules need the key of the same terminal, so it is
issued once per test session and the response kept: a second issue would leave
a module that still holds the first key with a key that no longer works.
"""
import os
from typing import Optional

import httpx
from httpx import AsyncClient

_issued: dict[str, httpx.Response] = {}


async def issue_terminal_api_key(
    terminal_id: str, headers: dict, base_url: Optional[str] = None
) -> httpx.Response:
    """
    POST /terminals/{terminal_id}/api-key, once per terminal per session

    Args:
        terminal_id: The terminal whose key to issue
        headers: A user JWT header; a terminal credential is refused
        base_url: Terminal service base URL, BASE_URL_TERMINAL by default

    Returns:
        The response, the same one on every call after the first success; the
        key is in .json()["data"]["apiKey"]
    """
    cached = _issued.get(terminal_id)
    if cached is not None:
        return cached
    base_url = base_url or os.environ.get("BASE_URL_TERMINAL")
    async with AsyncClient() as client:
        response = await client.post(f"{base_url}/terminals/{terminal_id}/api-key", headers=headers)
    if response.status_code == 200:
        _issued[terminal_id] = response
    return response

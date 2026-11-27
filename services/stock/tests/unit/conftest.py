# Copyright 2026 masa@kugel
"""Unit test conftest for stock service.

Unit tests have no external dependencies. Overrides set_env_vars to a
no-op and auto-marks all collected tests with `unit`.
"""
import os
import pytest


@pytest.fixture(scope="session")
def set_env_vars():
    yield


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory.

    pytest invokes the hook with the full `items` list collected from the
    whole session — without the path filter, the marker would apply to
    every test in the project, not just this tier.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def no_dead_letter_writes(request):
    """Unit tests never write a dead-letter record (#230).

    A failed subscription asks for redelivery, as it did before. The tests of
    the give-up path patch ``_record_failure`` themselves (marker
    ``dead_letter_writes``).
    """
    if request.node.get_closest_marker("dead_letter_writes"):
        yield
        return
    from unittest.mock import AsyncMock, patch

    with patch("app.api.v1.stock._record_failure", new_callable=AsyncMock, return_value=False), patch(
        "app.api.v1.stock.notify_unrecordable", new_callable=AsyncMock
    ):
        yield

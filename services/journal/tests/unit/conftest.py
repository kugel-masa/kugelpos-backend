# Copyright 2026 masa@kugel
"""Unit test conftest for journal service.

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

# Copyright 2026 masa@kugel
"""Unit test conftest for cart service.

Unit tests have no external dependencies. This conftest overrides the
parent set_env_vars fixture to a no-op so unit tests can run without
MongoDB, network, account, or terminal services.

Tests under this directory are auto-marked with `unit`.
"""
import os
import pytest


@pytest.fixture(scope="session")
def set_env_vars():
    """No-op override: unit tests need no environment setup."""
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

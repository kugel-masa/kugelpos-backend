# Copyright 2026 masa@kugel
"""Unit test conftest for master-data service.

Unit tests have no external dependencies. This conftest overrides the
parent set_env_vars fixture to a no-op so unit tests can run without
MongoDB, network, or any other service.

Tests under this directory are auto-marked with `unit`.
"""
import pytest


@pytest.fixture(scope="session")
def set_env_vars():
    """No-op override: unit tests need no environment setup."""
    yield


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.unit)

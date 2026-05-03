# Copyright 2026 masa@kugel
"""Unit test conftest for stock service.

Unit tests have no external dependencies. Overrides set_env_vars to a
no-op and auto-marks all collected tests with `unit`.
"""
import pytest


@pytest.fixture(scope="session")
def set_env_vars():
    yield


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.unit)

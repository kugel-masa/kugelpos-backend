# Copyright 2026 masa@kugel
"""E2E test conftest for report service.

Auto-marks tests with `e2e` and ensures test_setup_data runs first.
Inherits set_env_vars, http_client, clean_test_data, etc. from the
parent conftest (which does the full cross-service setup needed for
e2e tests).
"""
import pytest


def pytest_collection_modifyitems(config, items):
    setup_items = [i for i in items if "test_setup_data" in i.nodeid]
    other_items = [i for i in items if "test_setup_data" not in i.nodeid]
    items[:] = setup_items + other_items
    for item in items:
        item.add_marker(pytest.mark.e2e)

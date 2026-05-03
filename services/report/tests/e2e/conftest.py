# Copyright 2026 masa@kugel
"""E2E test conftest for report service.

Auto-marks tests with `e2e` and ensures test_setup_data runs first.
Inherits set_env_vars, http_client, clean_test_data, etc. from the
parent conftest (which does the full cross-service setup needed for
e2e tests).
"""
import os
import pytest


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory and ensure
    test_setup_data runs first within this tier.

    pytest invokes the hook with the full `items` list collected from the
    whole session — without the path filter, the marker would apply to
    every test in the project, not just this tier.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    own = []
    other = []
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.e2e)
            own.append(item)
        else:
            other.append(item)
    setups = [i for i in own if "test_setup_data" in i.nodeid]
    rest = [i for i in own if "test_setup_data" not in i.nodeid]
    items[:] = other + setups + rest

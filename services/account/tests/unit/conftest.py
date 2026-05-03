# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""
Unit test conftest for account service.

Unit tests have no external dependencies — they mock all I/O at the boundary.
This conftest overrides the parent set_env_vars fixture to be a no-op so
unit tests can run without MongoDB, network, or any environment file.

Tests under this directory are auto-marked with `unit`.
"""
import os
import pytest


@pytest.fixture(scope="session")
def set_env_vars():
    """No-op override of parent fixture: unit tests need no environment setup."""
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

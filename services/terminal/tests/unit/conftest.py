# Copyright 2026 masa@kugel
"""Unit test conftest for terminal service.

Unit tests have no external dependencies — they mock all I/O at the
boundary. This conftest overrides the parent set_env_vars fixture to be a
no-op so unit tests can run without MongoDB, network, or any environment
file.

Tests under this directory are auto-marked with `unit`.
"""
import pytest


@pytest.fixture(scope="session")
def set_env_vars():
    """No-op override: unit tests need no environment setup."""
    yield


def pytest_collection_modifyitems(config, items):
    """Auto-mark every test collected under tests/unit/ with `unit`."""
    for item in items:
        item.add_marker(pytest.mark.unit)

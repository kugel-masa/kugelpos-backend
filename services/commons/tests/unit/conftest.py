# Copyright 2026 masa@kugel
"""Unit test conftest for kugel_common.

kugel_common is a pure library — its unit tests have no external
dependencies and just need the package on sys.path (handled by
pytest.ini's `pythonpath = src`). Auto-marks every collected test in
this directory with `unit`.
"""
import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Mark only items located under THIS conftest's directory."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    for item in items:
        if str(item.fspath).startswith(this_dir):
            item.add_marker(pytest.mark.unit)

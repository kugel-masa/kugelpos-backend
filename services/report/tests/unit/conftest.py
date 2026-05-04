# Minimal conftest for unit tests — avoids the autouse fixtures in parent conftest.py
# that try to connect to external services.
import os
import pytest
import pytest_asyncio
from unittest.mock import patch


@pytest.fixture(scope="session")
def set_env_vars():
    """Override parent conftest set_env_vars to avoid external connections."""
    import os
    os.environ.setdefault("DB_NAME_PREFIX", "db_report_test")
    yield


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_connection(set_env_vars):
    """Override parent conftest cleanup_database_connection to avoid DB operations."""
    yield


@pytest.fixture(autouse=True)
def mock_locale():
    """Mock locale.setlocale to avoid locale errors in test environment."""
    with patch("locale.setlocale"):
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

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


@pytest.fixture(autouse=True)
def no_dead_letter_writes(request):
    """Unit tests never write a dead-letter record (#230).

    A failed subscription asks for redelivery, as it did before. The tests of
    the give-up path patch ``_record_failure`` themselves (marker
    ``dead_letter_writes``).
    """
    if request.node.get_closest_marker("dead_letter_writes"):
        yield
        return
    from unittest.mock import AsyncMock

    with patch("app.api.v1.tran._record_failure", new_callable=AsyncMock, return_value=False), patch(
        "app.api.v1.tran.notify_unrecordable", new_callable=AsyncMock
    ):
        yield

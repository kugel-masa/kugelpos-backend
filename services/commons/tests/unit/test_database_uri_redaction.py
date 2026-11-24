"""
Unit tests for keeping MongoDB credentials out of database error messages.
"""
import pytest

from kugel_common.database import database
from kugel_common.database.database import redact_uri
from kugel_common.database.database_exceptions import DatabaseException


@pytest.mark.parametrize(
    "uri, expected",
    [
        (
            "mongodb://user:secret@db.example.com:27017/?replicaSet=rs0",
            "mongodb://***:***@db.example.com:27017/?replicaSet=rs0",
        ),
        (
            "mongodb://user:p@ss@db.example.com:27017/",
            "mongodb://***:***@db.example.com:27017/",
        ),
        (
            "mongodb+srv://user:secret@cluster0.example.net/kugel",
            "mongodb+srv://***:***@cluster0.example.net/kugel",
        ),
    ],
)
def test_credentials_are_replaced_and_host_is_kept(uri, expected):
    assert redact_uri(uri) == expected


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://localhost:27017/?replicaSet=rs0",
        "mongodb://localhost:27017/?appname=ops@example.com",
    ],
)
def test_uri_without_credentials_is_unchanged(uri):
    assert redact_uri(uri) == uri


@pytest.mark.asyncio
async def test_failed_connection_message_has_no_credentials(monkeypatch):
    created = []

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            created.append(self)
            self.closed = False

        async def server_info(self):
            raise RuntimeError("unreachable")

        async def close(self):
            self.closed = True

    monkeypatch.setattr(database, "MONGODB_URI", "mongodb://kugel:s3cr3t@db.example.com:27017/")
    monkeypatch.setattr(database, "AsyncMongoClient", _FailingClient)
    monkeypatch.setattr(database, "client", None)

    with pytest.raises(DatabaseException) as exc:
        await database.get_db_async("db_test")

    message = str(exc.value)
    assert "s3cr3t" not in message
    assert "kugel:" not in message
    assert "db.example.com" in message
    assert "db_test" in message
    # The stand-in was the client actually used, and the failed client was closed
    assert created and all(c.closed for c in created)
    assert database.client is None

"""
Terminal API keys are stored as a digest and verified against it (issue #136).

A document written before the change still holds its plaintext key: it is
accepted, and sealed - digest written, plaintext removed - once verified.
"""
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from kugel_common.config.settings import settings
from kugel_common.security import get_terminal_info_for_terminal_service
from kugel_common.utils.terminal_api_key import (
    api_key_matches,
    hash_api_key,
    legacy_plaintext_api_key,
    seal_legacy_api_key_async,
)

KEY = "k3y-0123456789abcdefghijklmnopqrstuvwxyzABC"


def _hashed_doc(**overrides):
    doc = {
        "_id": "oid-1",
        "tenant_id": "T001",
        "store_code": "001",
        "terminal_no": 1,
        "terminal_id": "T001-001-01",
        "api_key_hash": hash_api_key(KEY),
    }
    doc.update(overrides)
    return doc


def _legacy_doc(**overrides):
    doc = _hashed_doc(api_key=KEY)
    del doc["api_key_hash"]
    doc.update(overrides)
    return doc


class TestDigest:
    def test_is_sha256_hex(self):
        assert hash_api_key(KEY) == hashlib.sha256(KEY.encode()).hexdigest()

    def test_hashed_document_matches_its_key_only(self):
        assert api_key_matches(_hashed_doc(), KEY)
        assert not api_key_matches(_hashed_doc(), KEY + "x")

    def test_the_digest_itself_is_not_a_key(self):
        """Someone holding the stored digest cannot present it as the key."""
        assert not api_key_matches(_hashed_doc(), hash_api_key(KEY))

    def test_legacy_document_matches_its_plaintext(self):
        assert api_key_matches(_legacy_doc(), KEY)
        assert not api_key_matches(_legacy_doc(), "other")

    def test_digest_wins_over_a_leftover_plaintext(self):
        doc = _hashed_doc(api_key="stale-plaintext")
        assert api_key_matches(doc, KEY)
        assert not api_key_matches(doc, "stale-plaintext")
        assert legacy_plaintext_api_key(doc) is None

    @pytest.mark.parametrize("presented", [None, "", 123, ["k"], "ключ"])
    def test_anything_else_is_refused_without_raising(self, presented):
        assert not api_key_matches(_hashed_doc(), presented)
        assert not api_key_matches(_legacy_doc(), presented)

    def test_a_document_without_any_key_matches_nothing(self):
        doc = _hashed_doc()
        del doc["api_key_hash"]
        assert not api_key_matches(doc, KEY)
        assert not api_key_matches(doc, "")


class TestSeal:
    @pytest.mark.asyncio
    async def test_writes_the_digest_and_removes_the_plaintext(self):
        collection = MagicMock()
        collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        assert await seal_legacy_api_key_async(collection, _legacy_doc())

        filter_, update = collection.update_one.await_args.args
        # Matched on the plaintext as read, so a key reissued meanwhile is kept
        assert filter_ == {"_id": "oid-1", "api_key": KEY}
        assert update == {"$set": {"api_key_hash": hash_api_key(KEY)}, "$unset": {"api_key": ""}}

    @pytest.mark.asyncio
    async def test_a_plaintext_left_beside_a_digest_is_removed(self):
        collection = MagicMock()
        collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        assert await seal_legacy_api_key_async(collection, _hashed_doc(api_key="leftover"))

        filter_, update = collection.update_one.await_args.args
        assert filter_ == {"_id": "oid-1", "api_key": "leftover"}
        assert update == {"$unset": {"api_key": ""}}

    @pytest.mark.asyncio
    async def test_nothing_is_written_while_sealing_is_off(self, monkeypatch):
        """Sealing is one-way; the setting keeps a rollback to a terminal service
        that only reads plaintext open."""
        monkeypatch.setattr(settings, "SEAL_LEGACY_TERMINAL_API_KEYS", False)
        collection = MagicMock()
        collection.update_one = AsyncMock()

        assert not await seal_legacy_api_key_async(collection, _legacy_doc())
        assert not await seal_legacy_api_key_async(collection, _hashed_doc(api_key="leftover"))
        collection.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_hashed_document_is_left_alone(self):
        collection = MagicMock()
        collection.update_one = AsyncMock()

        assert not await seal_legacy_api_key_async(collection, _hashed_doc())
        collection.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_write_is_swallowed(self):
        collection = MagicMock()
        collection.update_one = AsyncMock(side_effect=RuntimeError("db down"))

        assert not await seal_legacy_api_key_async(collection, _legacy_doc())


def _patched_db(doc):
    collection = MagicMock()
    collection.find_one = AsyncMock(return_value=doc)
    collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db = MagicMock()
    db.get_collection = MagicMock(return_value=collection)
    return collection, patch("kugel_common.security.db_helper.get_db_async", new=AsyncMock(return_value=db))


class TestVerificationInTheTerminalService:
    @pytest.mark.asyncio
    async def test_a_hashed_terminal_is_accepted_and_not_rewritten(self):
        collection, db_patch = _patched_db(_hashed_doc())
        with db_patch:
            terminal = await get_terminal_info_for_terminal_service("T001-001-01", KEY)

        assert terminal.terminal_id == "T001-001-01"
        # The caller's proven key, never the stored digest
        assert terminal.api_key == KEY
        collection.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_legacy_terminal_is_accepted_and_sealed(self):
        collection, db_patch = _patched_db(_legacy_doc())
        with db_patch:
            await get_terminal_info_for_terminal_service("T001-001-01", KEY)

        update = collection.update_one.await_args.args[1]
        assert update["$set"] == {"api_key_hash": hash_api_key(KEY)}

    @pytest.mark.asyncio
    async def test_a_legacy_terminal_is_still_accepted_while_sealing_is_off(self, monkeypatch):
        monkeypatch.setattr(settings, "SEAL_LEGACY_TERMINAL_API_KEYS", False)
        collection, db_patch = _patched_db(_legacy_doc())
        with db_patch:
            terminal = await get_terminal_info_for_terminal_service("T001-001-01", KEY)

        assert terminal.terminal_id == "T001-001-01"
        collection.update_one.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_wrong_key_is_refused(self):
        collection, db_patch = _patched_db(_hashed_doc())
        with db_patch:
            with pytest.raises(HTTPException) as exc:
                await get_terminal_info_for_terminal_service("T001-001-01", "wrong")

        assert exc.value.status_code == 401
        collection.update_one.assert_not_awaited()

# Copyright 2026 masa@kugel
"""abort_transaction must not replace the failure it is cleaning up after (#172).

Callers abort from an exception handler. A commit that fails leaves the session
set but past the point where it can be aborted, and the driver's complaint about
that ("Cannot call abortTransaction after calling commitTransaction") used to
surface instead of the error that actually broke the operation - a concurrent
duplicate finalize came back as a 500 whose message described the cleanup.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kugel_common.exceptions import RepositoryException
from kugel_common.models.repositories.abstract_repository import AbstractRepository


class _Repo(AbstractRepository):
    """Minimal concrete repository; only the session plumbing is exercised."""

    def __init__(self):
        super().__init__("test_collection", MagicMock, MagicMock())


def _session(in_transaction=True, abort_error=None, end_error=None):
    session = MagicMock()
    session.in_transaction = in_transaction
    session.abort_transaction = AsyncMock(side_effect=abort_error)
    session.end_session = AsyncMock(side_effect=end_error)
    return session


class TestAbortsWhatCanBeAborted:
    @pytest.mark.asyncio
    async def test_aborts_a_live_transaction(self):
        repo = _Repo()
        repo.session = session = _session()

        await repo.abort_transaction()

        session.abort_transaction.assert_awaited_once()
        session.end_session.assert_awaited_once()
        assert repo.session is None

    @pytest.mark.asyncio
    async def test_skips_the_abort_once_the_transaction_has_ended(self):
        # This is the committed-then-failed case: the session is still set, but
        # aborting it is what the driver refuses.
        repo = _Repo()
        repo.session = session = _session(in_transaction=False)

        await repo.abort_transaction()

        session.abort_transaction.assert_not_awaited()
        session.end_session.assert_awaited_once()
        assert repo.session is None


class TestNeverMasksTheOriginalFailure:
    @pytest.mark.asyncio
    async def test_a_refused_abort_does_not_raise(self):
        repo = _Repo()
        repo.session = _session(
            abort_error=RuntimeError("Cannot call abortTransaction after calling commitTransaction")
        )

        await repo.abort_transaction()  # must not raise

        assert repo.session is None

    @pytest.mark.asyncio
    async def test_a_failing_session_close_does_not_raise(self):
        repo = _Repo()
        repo.session = _session(end_error=RuntimeError("connection gone"))

        await repo.abort_transaction()  # must not raise

        assert repo.session is None

    @pytest.mark.asyncio
    async def test_the_session_is_released_even_when_cleanup_fails(self):
        # Otherwise the next request on this repository would think a
        # transaction is still in progress.
        repo = _Repo()
        repo.session = _session(abort_error=RuntimeError("boom"), end_error=RuntimeError("boom"))

        await repo.abort_transaction()

        assert repo.session is None


class TestNoTransaction:
    @pytest.mark.asyncio
    async def test_aborting_without_a_transaction_is_still_an_error(self):
        # A caller aborting when it never started one is a bug worth surfacing.
        repo = _Repo()
        repo.session = None

        with pytest.raises(RepositoryException):
            await repo.abort_transaction()

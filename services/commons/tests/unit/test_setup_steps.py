# Copyright 2026 masa@kugel
"""Running the tenant setup steps (issue #185).

Stopping at the first failing collection is worse than it looks: the collections
after it are never created either, so one blocked collection leaves the rest of
the tenant unset up — and the operator learns about the blocked ones one restart
at a time.

What these pin is that every step is attempted, that a failure names all of them,
and that an unreachable backend is still treated as different in kind.
"""

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from kugel_common.database.database import run_setup_steps_async
from kugel_common.database.database_exceptions import DatabaseException

pytestmark = pytest.mark.asyncio


def _step(name, fails_with=None, ran=None):
    async def step(tenant_id):
        if ran is not None:
            ran.append(name)
        if fails_with is not None:
            raise fails_with

    step.__name__ = name
    return step


class TestEveryStepIsAttempted:
    async def test_a_failing_step_does_not_stop_the_ones_after_it(self):
        ran = []
        steps = [
            _step("first", ran=ran),
            _step("blocked", RuntimeError("index cannot be built on log_tran"), ran=ran),
            _step("third", ran=ran),
            _step("fourth", ran=ran),
        ]

        with pytest.raises(DatabaseException):
            await run_setup_steps_async("T0001", steps)

        assert ran == ["first", "blocked", "third", "fourth"], (
            "a blocked collection stopped the healthy ones from being created"
        )

    async def test_all_the_failures_are_named_at_once(self):
        steps = [
            _step("ok"),
            _step("a", RuntimeError("log_tran: duplicate transaction_no 1 x4")),
            _step("b", RuntimeError("log_open_close: duplicate open_counter 1")),
        ]

        with pytest.raises(DatabaseException) as caught:
            await run_setup_steps_async("T0001", steps)

        message = str(caught.value)
        assert "log_tran" in message
        assert "log_open_close" in message, "only the first failure was reported"
        assert "2 of 3" in message

    async def test_nothing_is_raised_when_every_step_succeeds(self):
        ran = []
        await run_setup_steps_async("T0001", [_step("a", ran=ran), _step("b", ran=ran)])

        assert ran == ["a", "b"]

    async def test_the_tenant_reaches_every_step(self):
        seen = []

        async def step(tenant_id):
            seen.append(tenant_id)

        await run_setup_steps_async("T6216", [step, step])

        assert seen == ["T6216", "T6216"]


class TestAnUnreachableBackendIsDifferent:
    async def test_it_stops_immediately_rather_than_failing_every_step(self):
        # The remaining steps could only fail the same way, and a list of
        # identical connection errors describes nothing the first one did not.
        ran = []
        steps = [
            _step("first", ran=ran),
            _step("down", ServerSelectionTimeoutError("backend unreachable"), ran=ran),
            _step("never", ran=ran),
        ]

        with pytest.raises(ServerSelectionTimeoutError):
            await run_setup_steps_async("T0001", steps)

        assert ran == ["first", "down"], "setup carried on against an unreachable backend"

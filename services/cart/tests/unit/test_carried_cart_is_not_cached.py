# Copyright 2026 masa@kugel
"""A cart the client will carry is never written to the cache (issue #192).

Creation used to write unconditionally, because it has nothing to carry yet and
the server could not know whether the client would. That copy then sat there
while the carried requests moved the cart on, and one snapshot-less request
continued from it — dropping everything in between and answering with a
correctly signed snapshot of a cart missing it.

The client says at creation what it intends to do. When it will carry, nothing
is written, so there is no stale copy for such a request to continue from: it
finds no cart at all. The mixture stops being detectable and starts being
impossible.
"""

from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.test_cart_service import _build_service, _make_cart_doc

pytestmark = pytest.mark.asyncio


async def _create(service, carry_snapshot=None):
    service.cart_repo.create_cart_async = AsyncMock(return_value=_make_cart_doc(status="Initial", cart_id="c-192"))
    service.cart_repo.cache_cart_async = AsyncMock()
    kwargs = {} if carry_snapshot is None else {"carry_snapshot": carry_snapshot}
    await service.create_cart_async(terminal_id="t1-S001-1", transaction_type=1, user_id="u", user_name="U", **kwargs)
    return service


class TestWhatCreationWrites:
    async def test_a_carried_cart_is_not_written(self):
        service = await _create(_build_service(), carry_snapshot=True)

        service.cart_repo.cache_cart_async.assert_not_awaited()

    async def test_a_cart_the_client_will_not_carry_still_is(self):
        # The cache-authoritative path is what DUAL exists for; it needs the cart
        # to be there.
        service = await _create(_build_service(), carry_snapshot=False)

        service.cart_repo.cache_cart_async.assert_awaited_once()

    async def test_saying_nothing_means_not_carrying(self):
        # What a pre-#192 client means by omitting the field. Its behaviour has
        # to be exactly what it was.
        service = await _create(_build_service(), carry_snapshot=None)

        service.cart_repo.cache_cart_async.assert_awaited_once()


class TestTheResponseIsStillBuiltFromTheCart:
    async def test_the_created_cart_is_readable_without_the_cache(self):
        """The creation response carries a snapshot, which needs the document.

        It used to read it back from the cache — described in its own comment as
        "built from the cached (authoritative) cart". With nothing written there
        is nothing to read back, so the document has to come from the service
        itself.
        """
        service = await _create(_build_service(), carry_snapshot=True)
        service.cart_repo.get_cached_cart_async = AsyncMock(
            side_effect=AssertionError("the cache was read for a carried cart")
        )

        cart = await service.get_cart_async()

        assert cart.cart_id == "c-192"


class TestRequiredModeNeedsNoDeclaration:
    """Every mutating request has to carry, so a cached copy could never be read."""

    async def test_nothing_is_written_even_when_the_client_says_nothing(self):
        service = _build_service()
        with patch("app.services.cart_service.settings") as mocked:
            mocked.CART_REQUEST_SNAPSHOT_MODE = "REQUIRED"
            await _create(service, carry_snapshot=False)

        service.cart_repo.cache_cart_async.assert_not_awaited()

    async def test_dual_mode_still_honours_the_declaration(self):
        service = _build_service()
        with patch("app.services.cart_service.settings") as mocked:
            mocked.CART_REQUEST_SNAPSHOT_MODE = "DUAL"
            await _create(service, carry_snapshot=False)

        service.cart_repo.cache_cart_async.assert_awaited_once()


class TestCarryingACartThatWasNotOpenedForIt:
    """The other direction, and the reason the declaration is on the document.

    A cart opened for the cache path has its copy there, and a carried request
    would not update it — so the next snapshot-less request continues from a
    cart missing everything the carried ones did. Declaring one thing and doing
    the other has to be refused, not honoured.
    """

    def _snapshot_cart(self, carry_snapshot):
        cart = _make_cart_doc(status="Idle", cart_id="cart-001")
        cart.carry_snapshot = carry_snapshot
        return cart

    async def _present(self, service, cart):
        with patch("app.services.cart_service.snapshot_service") as snapshots:
            from app.services.snapshot_service import RESTORABLE_STATUSES

            snapshots.extract_audit_meta.return_value = {"cart_id": cart.cart_id}
            snapshots.verify_envelope.return_value = cart
            snapshots.RESTORABLE_STATUSES = RESTORABLE_STATUSES
            await service.prepare_stateless_from_snapshot(
                {"tenant_id": service.terminal_info.tenant_id, "store_code": service.terminal_info.store_code},
                api_path="/probe",
            )

    async def test_a_cart_opened_for_the_cache_cannot_be_carried(self):
        from app.exceptions import CartPathMismatchException

        service = _build_service()
        service.cart_restore_log_repo = None

        with pytest.raises(CartPathMismatchException):
            await self._present(service, self._snapshot_cart(carry_snapshot=False))

    async def test_a_cart_opened_to_be_carried_can_be(self):
        service = _build_service()
        service.cart_restore_log_repo = None

        await self._present(service, self._snapshot_cart(carry_snapshot=True))

        assert service._stateless is True

    async def test_a_cart_from_before_the_field_existed_is_left_alone(self):
        # Carts in flight across the deployment that introduces this have no
        # declaration either way, and must keep working.
        service = _build_service()
        service.cart_restore_log_repo = None

        await self._present(service, self._snapshot_cart(carry_snapshot=None))

        assert service._stateless is True

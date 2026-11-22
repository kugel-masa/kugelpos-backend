"""A payment master is read once per request (issue #311).

A payment is read for its variant and again when its strategy settles it. The
repository is built per request and keeps what it read, so the second read costs
no cache or master-data call and both see the same document.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kugel_common.exceptions import NotFoundException
from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend

from app.models.documents.payment_master_document import PaymentMasterDocument, PaymentVariant
from app.models.repositories.payment_master_web_repository import PaymentMasterWebRepository

pytestmark = pytest.mark.asyncio


def _repo(cache_backend=None) -> PaymentMasterWebRepository:
    terminal = MagicMock()
    terminal.tenant_id = "T1"
    terminal.store_code = "S1"
    repo = PaymentMasterWebRepository(tenant_id="T1", terminal_info=terminal, cache_backend=cache_backend)
    repo._fetch_one = AsyncMock(
        side_effect=lambda code: PaymentMasterDocument(
            payment_code=code, description="Cashless", variants=[PaymentVariant(variant_code="VISA", name="VISA")]
        )
    )
    return repo


@pytest.mark.parametrize("cache_backend", [None, InMemoryCacheBackend()], ids=["cache off", "cache on"])
async def test_a_payment_master_is_fetched_once_per_request(cache_backend):
    repo = _repo(cache_backend)

    first = await repo.get_payment_by_code_async("11")
    second = await repo.get_payment_by_code_async("11")

    assert repo._fetch_one.await_count == 1
    assert first == second


async def test_the_cache_is_not_asked_twice_either():
    backend = InMemoryCacheBackend()
    repo = _repo(backend)
    await repo.get_payment_by_code_async("11")
    backend.get = AsyncMock(wraps=backend.get)

    await repo.get_payment_by_code_async("11")

    backend.get.assert_not_awaited()


async def test_each_code_is_read_on_its_own():
    repo = _repo()

    await repo.get_payment_by_code_async("11")
    await repo.get_payment_by_code_async("12")

    assert [c.args[0] for c in repo._fetch_one.await_args_list] == ["11", "12"]


async def test_a_caller_changing_what_it_got_does_not_change_the_next_read():
    repo = _repo()

    first = await repo.get_payment_by_code_async("11")
    first.description = "changed"
    first.variants[0].name = "changed"

    second = await repo.get_payment_by_code_async("11")
    assert (second.description, second.variants[0].name) == ("Cashless", "VISA")


async def test_a_new_request_reads_again():
    first_request, second_request = _repo(), _repo()

    await first_request.get_payment_by_code_async("11")
    await second_request.get_payment_by_code_async("11")

    assert first_request._fetch_one.await_count == second_request._fetch_one.await_count == 1


async def test_an_unknown_code_is_not_remembered():
    repo = _repo()
    repo._fetch_one = AsyncMock(side_effect=NotFoundException("nf", "payment web", "99"))

    for _ in range(2):
        with pytest.raises(NotFoundException):
            await repo.get_payment_by_code_async("99")

    assert repo._fetch_one.await_count == 2

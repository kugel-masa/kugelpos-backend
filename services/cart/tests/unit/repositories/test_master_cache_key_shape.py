# Copyright 2026 masa@kugel
"""A cached master entry is read only by the model shape that wrote it.

An entry is the model_dump of the model that wrote it. Without the model's shape
in the key, a cart whose model gained a field read entries an older cart wrote:
a field with a default came back as that default, and one without a default (or
a retyped field) failed validation on every lookup, until the TTL ran out. In a
rolling deploy the old and new carts read each other's entries the same way.
"""

import pytest
from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.utils.cache.in_memory_cache_backend import InMemoryCacheBackend
from pydantic import Field

from app.models.repositories.abstract_master_data_repository import (
    AbstractMasterDataRepository,
    document_shape,
)


class _Terminal:
    store_code = "S1"


class OldDoc(BaseDocumentModel):
    code: str
    value: int


class GainedDefaultDoc(BaseDocumentModel):
    code: str
    value: int
    variants: list[str] = Field(default_factory=list)


class GainedRequiredDoc(BaseDocumentModel):
    code: str
    value: int
    rate: float


class Nested(BaseDocumentModel):
    a: int


class NestedOld(BaseDocumentModel):
    inner: Nested


class Nested2(BaseDocumentModel):
    a: int
    b: int = 0


class NestedNew(BaseDocumentModel):
    inner: Nested2


def _repo_for(document_cls, backend, value_factory):
    class Repo(AbstractMasterDataRepository[document_cls]):
        cache_namespace = "shape_test"
        document_class = document_cls
        default_ttl_seconds = 60
        is_store_scoped = True

        def __init__(self):
            super().__init__(tenant_id="T1", terminal_info=_Terminal(), cache_backend=backend, store_code="S1")
            self.fetch_calls = 0

        async def _fetch_one(self, logical_key):
            self.fetch_calls += 1
            return value_factory(logical_key)

    return Repo()


def test_shape_is_stable_for_the_same_model():
    assert document_shape(OldDoc) == document_shape(OldDoc)


@pytest.mark.parametrize("changed", [GainedDefaultDoc, GainedRequiredDoc])
def test_shape_changes_when_a_field_is_added(changed):
    assert document_shape(changed) != document_shape(OldDoc)


def test_shape_changes_when_a_nested_model_changes():
    assert document_shape(NestedOld) != document_shape(NestedNew)


def test_the_key_carries_the_shape():
    repo = _repo_for(OldDoc, InMemoryCacheBackend(), lambda k: OldDoc(code=k, value=1))
    key = repo._build_key("S1", 0, "one", "X")
    assert f":gen0:s{document_shape(OldDoc)}:one:X" in key


@pytest.mark.asyncio
async def test_a_model_that_gained_a_defaulted_field_does_not_read_the_old_entry():
    backend = InMemoryCacheBackend()
    old = _repo_for(OldDoc, backend, lambda k: OldDoc(code=k, value=1))
    await old.get_or_fetch_one("P1")

    new = _repo_for(GainedDefaultDoc, backend, lambda k: GainedDefaultDoc(code=k, value=1, variants=["v"]))
    doc = await new.get_or_fetch_one("P1")

    assert new.fetch_calls == 1, "the new model read the old model's entry instead of fetching"
    assert doc.variants == ["v"]


@pytest.mark.asyncio
async def test_a_model_that_gained_a_required_field_does_not_fail_on_the_old_entry():
    backend = InMemoryCacheBackend()
    old = _repo_for(OldDoc, backend, lambda k: OldDoc(code=k, value=1))
    await old.get_or_fetch_one("P1")

    new = _repo_for(GainedRequiredDoc, backend, lambda k: GainedRequiredDoc(code=k, value=1, rate=0.1))
    doc = await new.get_or_fetch_one("P1")

    assert doc.rate == 0.1


@pytest.mark.asyncio
async def test_the_same_model_still_hits_its_own_entry():
    backend = InMemoryCacheBackend()
    first = _repo_for(OldDoc, backend, lambda k: OldDoc(code=k, value=1))
    await first.get_or_fetch_one("P1")

    second = _repo_for(OldDoc, backend, lambda k: OldDoc(code=k, value=2))
    doc = await second.get_or_fetch_one("P1")

    assert second.fetch_calls == 0
    assert doc.value == 1

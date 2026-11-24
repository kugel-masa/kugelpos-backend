# Copyright 2026 masa@kugel
"""A minimal concrete repository for the integration tests."""
from typing import Optional

from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.models.repositories.abstract_repository import AbstractRepository


class SampleDocument(AbstractDocument):
    key: str
    group: Optional[str] = None
    amount: int = 0


class SampleRepository(AbstractRepository[SampleDocument]):
    def __init__(self, db, collection_name: str = "sample"):
        super().__init__(collection_name, SampleDocument, db)


async def make_repository(db, collection_name: str = "sample") -> SampleRepository:
    repo = SampleRepository(db, collection_name)
    await repo.initialize()
    return repo

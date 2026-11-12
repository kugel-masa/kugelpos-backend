# Copyright 2026 masa@kugel
"""Store a log once, on its natural key, without depending on the unique index.

The log writers used to read and then insert. That deduplicates only while the
collection's unique index exists: a delivery that arrives before tenant setup
(or after the tenant database was dropped) makes MongoDB create the collection
with no index, concurrent deliveries all see "not present" and all insert, and
from then on the index can never be built - tenant setup keeps failing (#185)
and a report counts the sale twice. Measured: 4 concurrent deliveries, no
index, duplicates in 100 of 100 trials.

A single upsert on the natural key replaces the read and the insert, and the
inserted document's ``_id`` is derived from that key. An upsert alone does not
make concurrent inserts unique when there is no unique index, but ``_id`` always
has one, from the moment the collection exists: of two concurrent deliveries
only one can insert, and the other gets E11000 on ``_id``, which means "already
stored". The lookup stays on the natural key, so a log stored before this
change (with a generated ObjectId) is still found and not stored again.
"""

import hashlib
import json

from kugel_common.models.documents.base_document_model import BaseDocumentModel
from kugel_common.models.repositories.abstract_repository import AbstractRepository
from kugel_common.utils.misc import get_app_time
from pymongo.errors import DuplicateKeyError


def natural_key_id(key: dict) -> str:
    """The ``_id`` a log stored on ``key`` gets: the same key always gives the same id."""
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode("utf-8")).hexdigest()


async def insert_if_absent(repo: AbstractRepository, key: dict, document: BaseDocumentModel) -> bool:
    """Insert ``document`` unless a document matching ``key`` exists.

    Runs in the repository's session when it has one, so it can be part of a
    transaction; matching an existing document does not raise, so it does not
    abort one. A concurrent insert of the same key does: MongoDB aborts the
    transaction on E11000, so inside a transaction the error is raised for the
    caller to abort and retry, as it already does for this case (issue #230).

    ``document`` is changed only when it was inserted: its ``created_at`` is set
    then, so a redelivery returns the input untouched.

    Args:
        repo: The repository whose collection and session to use
        key: The natural key the collection's unique index covers
        document: The document to store

    Returns:
        True if the document was inserted, False if one was already stored.
    """
    if repo.dbcollection is None:
        await repo.initialize()
    created_at = get_app_time()
    values = document.model_dump()
    values["created_at"] = created_at
    values["_id"] = natural_key_id(key)
    try:
        result = await repo.dbcollection.update_one(
            key, {"$setOnInsert": values}, upsert=True, session=repo.session
        )
    except DuplicateKeyError:
        # A concurrent delivery inserted it first (E11000 on _id, or on the
        # unique index once that exists).
        if repo.session is not None:
            raise
        return False
    if result.upserted_id is None:
        return False
    document.created_at = created_at
    return True

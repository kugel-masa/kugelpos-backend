# Copyright 2026 masa@kugel
"""A journal keyword is searched as text, not as a regular expression (issue #138).

The keywords were joined into a $regex as given, so a caller could match journals
it did not name, and a pattern such as (a+)+$ could keep the database
backtracking over every journal it scans. Against MongoDB, because the pattern
is interpreted there, not in Python.
"""

import os

import pytest
import pytest_asyncio

from app.models.repositories.journal_repository import JournalRepository

TENANT = "JKEYWORD1"


@pytest_asyncio.fixture
async def repo():
    from kugel_common.database import database as db_helper

    db_name = f"{os.environ.get('DB_NAME_PREFIX')}_{TENANT}"
    client = await db_helper.get_client_async()
    await client.drop_database(db_name)
    db = await db_helper.get_db_async(db_name)
    repository = JournalRepository(db, TENANT)
    await repository.initialize()
    texts = [
        "milk 1,000円",
        "price (a+)+$ tag",
        "bread .* special",
        "item #12 back\\slash",
        "全角　１，０００円",
        "MILK upper",
    ]
    for receipt_no, text in enumerate(texts, start=1):
        await repository.dbcollection.insert_one(
            {
                "tenant_id": TENANT,
                "store_code": "S1",
                "terminal_no": 1,
                "transaction_type": 101,
                "business_date": "20261121",
                "open_counter": 1,
                "business_counter": receipt_no,
                "generate_date_time": f"2026-11-21T10:00:0{receipt_no}",
                "receipt_no": receipt_no,
                "receipt_text": "",
                "journal_text": text,
            }
        )
    try:
        yield repository
    finally:
        await client.drop_database(db_name)


async def _texts(repo, keywords):
    journals = await repo.get_journals_async(store_code="S1", keywords=keywords, limit=10, page=1, sort=[("receipt_no", 1)])
    texts = sorted(journal.journal_text for journal in journals)
    # The endpoint uses the paginated search, which also counts: same answer
    page = await repo.get_journals_paginated_async(
        store_code="S1", keywords=keywords, limit=10, page=1, sort=[("receipt_no", 1)]
    )
    assert sorted(journal.journal_text for journal in page.data) == texts
    assert page.metadata.total == len(texts)
    return texts


@pytest.mark.asyncio
async def test_a_pattern_matches_only_journals_that_contain_it(repo):
    assert await _texts(repo, [".*"]) == ["bread .* special"]
    assert await _texts(repo, ["(a+)+$"]) == ["price (a+)+$ tag"]


@pytest.mark.asyncio
async def test_plain_keywords_still_match_any_of_them(repo):
    assert await _texts(repo, ["milk", "bread"]) == ["bread .* special", "milk 1,000円"]
    assert await _texts(repo, ["1,000円"]) == ["milk 1,000円"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keyword, expected",
    [
        ("#12", ["item #12 back\\slash"]),
        ("back\\slash", ["item #12 back\\slash"]),
        ("全角　１，０００", ["全角　１，０００円"]),
        ("$ tag", ["price (a+)+$ tag"]),
    ],
    ids=["hash", "backslash", "full-width-and-ideographic-space", "dollar-and-space"],
)
async def test_characters_python_escapes_match_themselves_in_mongodb(repo, keyword, expected):
    """re.escape is Python's; the pattern is run by MongoDB's PCRE2."""
    assert await _texts(repo, [keyword]) == expected


@pytest.mark.asyncio
async def test_the_match_is_case_sensitive_as_before(repo):
    assert await _texts(repo, ["milk"]) == ["milk 1,000円"]
    assert await _texts(repo, ["MILK"]) == ["MILK upper"]

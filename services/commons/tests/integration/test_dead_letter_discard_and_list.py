# Copyright 2026 masa@kugel
"""Discard racing a replay, and the list's index use and tenant isolation (#230).

US3: a replay and a discard of the same pending record never both go through.
US4: the list filters run on the list indexes, and a tenant's list reads only
that tenant's database.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from kugel_common.dead_letter import router as router_module
from kugel_common.dead_letter.document import (
    COLLECTION,
    STATE_DISCARDED,
    STATE_PENDING,
    STATE_REPLAYED,
)
from kugel_common.dead_letter.outcome import HandlerOutcome
from kugel_common.dead_letter.replay import ReplayConflict, replay_one
from kugel_common.dead_letter.repository import (
    DeadLetterRepository,
    create_dead_letter_collections_async,
)
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_user_with_token

pytestmark = pytest.mark.asyncio


def record(event_id, state=STATE_PENDING, topic="topic-tranlog", tenant_id="T1", dead_at=None, **extra):
    dead_at = dead_at or datetime.now(timezone.utc)
    return {
        "_id": event_id,
        "event_id": event_id,
        "tenant_id": tenant_id,
        "service": "report",
        "topic": topic,
        "state": state,
        "failure_count": 17,
        "episode_failure_count": 17,
        "dead_count": 1,
        "first_dead_at": dead_at,
        "last_dead_at": dead_at,
        "notified_at": dead_at,
        "summary": {"store_code": "5001"},
        "last_error": "RuntimeError",
        "message": {"data": {"event_id": event_id, "tenant_id": tenant_id}},
        **extra,
    }


# -- US3: discard and replay at the same time --------------------------------


async def test_a_discard_during_a_replay_is_refused_and_the_replay_wins(test_db):
    await test_db[COLLECTION].insert_one(record("e-1"))
    repo = DeadLetterRepository(test_db)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(message, topic):
        started.set()
        await release.wait()
        return HandlerOutcome.processed()

    replay = asyncio.create_task(replay_one(db=test_db, event_id="e-1", user="alice", core=slow))
    await started.wait()
    assert await repo.discard("e-1", "bob", "test data") is None
    release.set()
    assert (await replay).outcome == "replayed"
    doc = await test_db[COLLECTION].find_one({"_id": "e-1"})
    assert doc["state"] == STATE_REPLAYED and doc["resolved_by"] == "alice"
    assert doc.get("resolution_note") is None


async def test_a_replay_after_a_discard_is_a_conflict_and_never_runs_the_handler(test_db):
    await test_db[COLLECTION].insert_one(record("e-1"))
    repo = DeadLetterRepository(test_db)
    assert (await repo.discard("e-1", "bob", "test data"))["state"] == STATE_DISCARDED
    calls = []

    async def core(message, topic):
        calls.append(1)
        return HandlerOutcome.processed()

    with pytest.raises(ReplayConflict):
        await replay_one(db=test_db, event_id="e-1", user="alice", core=core)
    assert calls == []
    assert (await test_db[COLLECTION].find_one({"_id": "e-1"}))["state"] == STATE_DISCARDED


async def test_a_racing_claim_and_discard_let_exactly_one_through(test_db):
    repo = DeadLetterRepository(test_db)
    ids = [f"e-{i}" for i in range(30)]
    await test_db[COLLECTION].insert_many([record(i) for i in ids])

    for event_id in ids:
        claimed, discarded = await asyncio.gather(
            repo.claim_replay(event_id, f"claim-{event_id}"),
            repo.discard(event_id, "bob", "race"),
        )
        assert (claimed is None) != (discarded is None), event_id


# -- US4: the list ------------------------------------------------------------


def _winning_stages(plan: dict) -> list[dict]:
    """Every stage of a winning plan, depth first."""
    stages = [plan]
    for key in ("inputStage", "queryPlan"):
        if key in plan:
            stages += _winning_stages(plan[key])
    for child in plan.get("inputStages", []):
        stages += _winning_stages(child)
    return stages


async def _index_used(db, query: dict) -> str | None:
    cursor = db[COLLECTION].find(query).sort([("last_dead_at", -1), ("_id", 1)]).limit(50)
    explained = await cursor.explain()
    winning = explained["queryPlanner"]["winningPlan"]
    for stage in _winning_stages(winning):
        if stage.get("stage") == "IXSCAN":
            return stage["indexName"]
    return None


@pytest.mark.parametrize(
    "query",
    [
        {"state": {"$in": [STATE_PENDING]}},
        {"state": {"$in": [STATE_PENDING, "replaying"]}, "notified_at": None},
        {"state": {"$in": [STATE_PENDING]}, "topic": "topic-cashlog"},
        {"state": {"$in": [STATE_PENDING]}, "last_dead_at": {"$gte": datetime(2026, 1, 1, tzinfo=timezone.utc)}},
    ],
)
async def test_the_list_filters_run_on_an_index(test_db, query):
    await create_dead_letter_collections_async(test_db.name)
    base = datetime.now(timezone.utc)
    await test_db[COLLECTION].insert_many(
        [
            record(
                f"e-{i}",
                state=(STATE_PENDING, STATE_REPLAYED, "failing")[i % 3],
                topic=("topic-tranlog", "topic-cashlog")[i % 2],
                dead_at=base - timedelta(minutes=i),
            )
            for i in range(200)
        ]
    )
    assert await _index_used(test_db, query) is not None


async def test_a_tenants_list_reads_only_that_tenants_database(test_db, db_helper):
    client = await db_helper.get_client_async()
    other = client[f"{test_db.name}_t2"]
    try:
        await test_db[COLLECTION].insert_one(record("mine", tenant_id="T1"))
        await other[COLLECTION].insert_one(record("theirs", tenant_id="T2"))
        opened = []

        async def get_db(name):
            opened.append(name)
            return {"db_report_T1": test_db, "db_report_T2": other}[name]

        async def core(message, topic):
            return HandlerOutcome.processed()

        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(
            router_module.build_dead_letter_router(
                service="report", db_name_prefix="db_report", conflict_error_code="413009", core=core
            ),
            prefix="/api/v1",
        )
        user = {"username": "alice", "tenant_id": "T1"}
        app.dependency_overrides[get_user_with_token] = lambda: user
        original = router_module.db_helper.get_db_async
        router_module.db_helper.get_db_async = get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
                mine = await http.get("/api/v1/tenants/T1/dead-letters")
                theirs_record = await http.get("/api/v1/tenants/T1/dead-letters/theirs")
                forbidden = await http.get("/api/v1/tenants/T2/dead-letters")
        finally:
            router_module.db_helper.get_db_async = original

        assert mine.status_code == 200
        ids = [item["eventId"] for item in mine.json()["data"]]
        assert ids == ["mine"]
        assert theirs_record.status_code == 404
        assert forbidden.status_code == 403
        assert set(opened) == {"db_report_T1"}
    finally:
        await client.drop_database(other.name)

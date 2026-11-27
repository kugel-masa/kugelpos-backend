# Copyright 2026 masa@kugel
"""The dead-letter API against a real MongoDB (contracts/dead-letter-api.md)."""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from kugel_common.dead_letter import router as router_module
from kugel_common.dead_letter.document import COLLECTION
from kugel_common.dead_letter.outcome import HandlerOutcome
from kugel_common.exceptions import register_exception_handlers
from kugel_common.security import get_user_with_token

pytestmark = pytest.mark.asyncio

CONFLICT = "413009"


def record(event_id, state="pending", **extra):
    now = datetime.now(timezone.utc)
    return {
        "_id": event_id,
        "event_id": event_id,
        "tenant_id": "T1",
        "service": "report",
        "topic": "topic-tranlog",
        "state": state,
        "failure_count": 17,
        "dead_count": 1,
        "last_dead_at": now,
        "first_dead_at": now,
        "summary": {"store_code": "5001", "terminal_no": 1},
        "last_error": "RuntimeError",
        "message": {"data": {"event_id": event_id, "tenant_id": "T1", "terminal_info": {"api_key": "secret-key"}}},
        **extra,
    }


@pytest.fixture
def outcomes():
    return {"next": HandlerOutcome.processed()}


@pytest.fixture
def app(test_db, monkeypatch, outcomes):
    async def get_db(name):
        assert name == "db_report_T1"
        return test_db

    monkeypatch.setattr(router_module.db_helper, "get_db_async", get_db)

    async def core(message, topic):
        return outcomes["next"]

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(
        router_module.build_dead_letter_router(
            service="report", db_name_prefix="db_report", conflict_error_code=CONFLICT, core=core
        ),
        prefix="/api/v1",
    )
    app.dependency_overrides[get_user_with_token] = lambda: {"username": "alice", "tenant_id": "T1"}
    return app


async def request(app, method, path, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, f"/api/v1/tenants/T1/dead-letters{path}", **kwargs)


async def test_the_list_shows_pending_records_newest_first_without_content(app, test_db):
    await test_db[COLLECTION].insert_many(
        [record("a"), record("b", state="replayed"), record("c", state="failing"), record("d")]
    )
    body = (await request(app, "GET", "")).json()
    assert {r["id"] for r in body["data"]} == {"a", "d"}
    assert body["metadata"]["total"] == 2
    assert all("message" not in r for r in body["data"])
    assert body["data"][0]["eventId"] in ("a", "d") and "lastDeadAt" in body["data"][0]
    every = (await request(app, "GET", "?state=all")).json()
    assert every["metadata"]["total"] == 3  # failing is never listed
    assert (await request(app, "GET", "?state=bogus")).status_code == 422
    assert (await request(app, "GET", "?limit=201")).status_code == 422


async def test_the_list_filters_unnotified_records(app, test_db):
    await test_db[COLLECTION].insert_many([record("a", notified_at=datetime.now(timezone.utc)), record("b")])
    body = (await request(app, "GET", "?notified=false")).json()
    assert [r["id"] for r in body["data"]] == ["b"]


async def test_a_record_shows_its_content_masked(app, test_db):
    await test_db[COLLECTION].insert_one(record("a"))
    body = (await request(app, "GET", "/a")).json()
    assert body["data"]["message"]["data"]["event_id"] == "a"
    assert "secret-key" not in str(body)
    assert (await request(app, "GET", "/missing")).json()["userError"]["code"] == "100001"


async def test_another_tenants_user_is_forbidden(app):
    app.dependency_overrides[get_user_with_token] = lambda: {"username": "bob", "tenant_id": "T2"}
    assert (await request(app, "GET", "")).status_code == 403


async def test_replay_one(app, test_db, outcomes):
    await test_db[COLLECTION].insert_one(record("a"))
    outcomes["next"] = HandlerOutcome.failed(RuntimeError("x"))
    failed = await request(app, "POST", "/a/replay")
    assert failed.status_code == 200 and failed.json()["data"]["outcome"] == "failed"
    outcomes["next"] = HandlerOutcome.processed()
    done = await request(app, "POST", "/a/replay")
    assert done.json()["data"] == {"id": "a", "outcome": "replayed", "error": None}
    stored = await test_db[COLLECTION].find_one({"_id": "a"})
    assert stored["state"] == "replayed" and stored["resolved_by"] == "alice"
    again = await request(app, "POST", "/a/replay")
    assert again.status_code == 409 and again.json()["userError"]["code"] == CONFLICT
    assert (await request(app, "POST", "/missing/replay")).status_code == 404


async def test_replay_many_is_accepted_and_runs_in_the_background(app, test_db):
    await test_db[COLLECTION].insert_many([record("a"), record("b"), record("c", state="replayed")])
    response = await request(app, "POST", "/replay", json={"ids": ["a", "b", "a", "c", "missing"]})
    assert response.status_code == 202
    assert response.json()["data"]["accepted"] == ["a", "b", "c", "missing"]
    for _ in range(50):
        states = {d["_id"]: d["state"] async for d in test_db[COLLECTION].find({})}
        if states["a"] == states["b"] == "replayed":
            break
        await asyncio.sleep(0.05)
    assert states == {"a": "replayed", "b": "replayed", "c": "replayed"}
    assert (await request(app, "POST", "/replay", json={"ids": []})).status_code == 422
    assert (await request(app, "POST", "/replay", json={"ids": [str(i) for i in range(101)]})).status_code == 422


async def test_discard(app, test_db):
    await test_db[COLLECTION].insert_many([record("a"), record("b", state="replayed")])
    assert (await request(app, "POST", "/a/discard", json={"reason": "  "})).status_code == 422
    done = await request(app, "POST", "/a/discard", json={"reason": "test data"})
    assert done.status_code == 200 and done.json()["data"]["state"] == "discarded"
    assert done.json()["data"]["resolvedBy"] == "alice"
    assert (await request(app, "POST", "/b/discard", json={"reason": "x"})).status_code == 409
    assert (await request(app, "POST", "/missing/discard", json={"reason": "x"})).status_code == 404

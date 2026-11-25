# Copyright 2026 masa@kugel
"""A refused daily report names the unsettled sessions in data (#343, R-16)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kugel_common.exceptions import register_exception_handlers

from app.exceptions.report_exceptions import SessionNotSettledException
from app.exceptions.settlement_exception_handlers import register_settlement_exception_handlers

SESSIONS = [{"terminalNo": 2, "businessCounter": 7, "businessDate": "20261124", "openCounter": 1}]


def _client():
    app = FastAPI()
    register_exception_handlers(app)
    register_settlement_exception_handlers(app)

    @app.get("/daily")
    async def daily():
        raise SessionNotSettledException("not settled", SESSIONS)

    return TestClient(app)


def test_403_412101_with_the_unsettled_sessions():
    response = _client().get("/daily")

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["userError"]["code"] == "412101"
    assert body["data"] == {"unsettledSessions": SESSIONS}

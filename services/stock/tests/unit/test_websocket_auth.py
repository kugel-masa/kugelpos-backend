"""The stock alert WebSocket holds a terminal JWT to its own store (issue #331)."""

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.terminal_auth import create_terminal_token

from app.api.v1.stock import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _terminal_token(store_code: str) -> str:
    return create_terminal_token(TerminalInfoDocument(
        tenant_id="T001", store_code=store_code, terminal_no=1, terminal_id=f"T001-{store_code}-1", status="Opened",
    ))


def _close_reason(token: str, store_code: str = "5001", tenant_id: str = "T001") -> str:
    with _client().websocket_connect(f"/api/v1/ws/{tenant_id}/{store_code}?token={token}") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 1008
    return exc.value.reason


def test_a_terminal_jwt_of_another_store_is_refused():
    assert _close_reason(_terminal_token("5002")) == "Store mismatch"


def test_a_terminal_jwt_of_another_tenant_is_refused():
    assert _close_reason(_terminal_token("5001"), tenant_id="T999") == "Tenant ID mismatch"


def test_a_user_jwt_of_another_tenant_is_refused():
    token = jwt.encode({"sub": "admin", "tenant_id": "T999"}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert _close_reason(token) == "Tenant ID mismatch"


@pytest.mark.parametrize("make_token", [lambda: _terminal_token("5001"),
                                        lambda: jwt.encode({"sub": "admin", "tenant_id": "T001"},
                                                           settings.SECRET_KEY, algorithm=settings.ALGORITHM)],
                         ids=["terminal-own-store", "user-jwt"])
def test_an_allowed_token_gets_past_authentication(make_token, monkeypatch):
    # Past authentication the handler asks for the alert service; standing in a
    # missing one ends the connection with 1011 instead of an auth refusal.
    monkeypatch.setattr("app.dependencies.get_alert_service.get_alert_service", lambda: None)
    with _client().websocket_connect(f"/api/v1/ws/T001/5001?token={make_token()}") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 1011


def test_another_tenant_is_refused_before_the_store_is_looked_at():
    assert _close_reason(_terminal_token("5002"), tenant_id="T999") == "Tenant ID mismatch"


def test_a_terminal_jwt_without_a_store_is_refused():
    token = jwt.encode(
        {"sub": "terminal:T001-x-1", "tenant_id": "T001", "terminal_id": "T001-x-1", "token_type": "terminal"},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )
    assert _close_reason(token) == "Store mismatch"


def test_an_expired_terminal_jwt_fails_authentication():
    from datetime import timedelta

    token = create_terminal_token(
        TerminalInfoDocument(tenant_id="T001", store_code="5001", terminal_no=1, terminal_id="T001-5001-1",
                             status="Opened"),
        expires_delta=timedelta(seconds=-1),
    )
    assert _close_reason(token) == "Authentication failed"

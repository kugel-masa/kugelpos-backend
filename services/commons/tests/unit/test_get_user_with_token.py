# Copyright 2026 masa@kugel
"""Only a signed-in user may call the dead-letter API (#230, R-9)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
import jwt

from kugel_common.security import ALGORITHM, SECRET_KEY, get_user_with_token

pytestmark = pytest.mark.asyncio


def token(**claims):
    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/who")
    async def who(user: dict = Depends(get_user_with_token)):
        return user

    return app


async def call(app, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/who", headers=headers or {})


async def test_a_user_token_gives_the_user_and_tenant(app):
    response = await call(app, {"Authorization": f"Bearer {token(sub='alice', tenant_id='T1')}"})
    assert response.status_code == 200
    assert response.json() == {"username": "alice", "tenant_id": "T1"}


async def test_no_token_is_401(app):
    assert (await call(app)).status_code == 401
    assert (await call(app, {"X-API-KEY": "terminal-key"})).status_code == 401


async def test_a_service_account_token_is_403(app):
    service = token(sub="report", tenant_id="T1", is_service_account=True, service="report")
    assert (await call(app, {"Authorization": f"Bearer {service}"})).status_code == 403


async def test_a_terminal_token_is_403(app):
    from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
    from kugel_common.utils.terminal_auth import create_terminal_token

    terminal = create_terminal_token(
        TerminalInfoDocument(tenant_id="T1", store_code="5001", terminal_no=1, terminal_id="T1-5001-1")
    )
    assert (await call(app, {"Authorization": f"Bearer {terminal}"})).status_code == 403


async def test_a_bad_token_is_401(app):
    assert (await call(app, {"Authorization": "Bearer not-a-token"})).status_code == 401

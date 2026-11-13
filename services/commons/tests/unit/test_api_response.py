"""Error responses carry userError, and the deprecated user_error during the transition.

A route's response goes through FastAPI's response_model and is written with the
aliases, so it answers ``userError``. The error bodies built by hand called
``model_dump()`` without them, so only an error answered ``user_error``: a client
following the naming convention could not read the error code exactly when it
needed it. They now write ``userError``, and ``user_error`` alongside it until
clients have moved over; ``user_error`` is deprecated.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from kugel_common.exceptions.base_exceptions import AppException
from kugel_common.exceptions.exception_handlers import register_exception_handlers
from kugel_common.schemas.api_response import ApiResponse, UserError


def test_to_response_body_writes_both_names_with_the_same_content():
    body = ApiResponse(
        success=False, code=400, message="m", user_error=UserError(code="401001", message="x"), data=None
    ).to_response_body()

    assert body["userError"] == {"code": "401001", "message": "x"}
    assert body["user_error"] == body["userError"]


def test_to_response_body_without_a_user_error_writes_null_under_both_names():
    body = ApiResponse(success=False, code=500, message="m", data=None).to_response_body()

    assert body["userError"] is None
    assert body["user_error"] is None


class _Body(BaseModel):
    n: int


def _app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http")
    async def http():
        raise HTTPException(status_code=404, detail="nope")

    @app.post("/request-validation")
    async def request_validation(body: _Body):
        return body

    @app.get("/validation")
    async def validation():
        _Body(n="not a number")

    @app.get("/app")
    async def app_error():
        raise AppException("boom", error_code="401001", status_code=400)

    @app.get("/unexpected")
    async def unexpected():
        raise RuntimeError("boom")

    return app


@pytest.mark.parametrize(
    "method, path",
    [("get", "/http"), ("post", "/request-validation"), ("get", "/validation"), ("get", "/app"), ("get", "/unexpected")],
)
def test_every_exception_handler_answers_with_both_names(method, path):
    client = TestClient(_app(), raise_server_exceptions=False)

    body = getattr(client, method)(path, json={}).json() if method == "post" else client.get(path).json()

    assert body["success"] is False
    assert "userError" in body, body
    assert body["user_error"] == body["userError"]

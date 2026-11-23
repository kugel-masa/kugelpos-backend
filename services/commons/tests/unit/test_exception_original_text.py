"""The original exception's text stays out of error responses, and its echoed values out of logs (#318)."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure, WriteError

from kugel_common.exceptions import AppException, RepositoryException, ServiceException
from kugel_common.exceptions.exception_handlers import register_exception_handlers
from kugel_common.utils.log_utils import describe_exception

PIN = "9876"


class _Staff(BaseModel):
    pin: str


def _validation_error() -> ValidationError:
    try:
        _Staff(pin=int(PIN))
    except ValidationError as e:
        return e
    raise AssertionError("expected a ValidationError")


def _duplicate_key_error() -> DuplicateKeyError:
    return DuplicateKeyError(
        f"E11000 duplicate key error collection: db.staff index: pin_1 dup key: {{ pin: \"{PIN}\" }}",
        11000,
        {"code": 11000, "codeName": "DuplicateKey", "keyPattern": {"pin": 1}, "keyValue": {"pin": PIN}},
    )


class TestDescribeException:
    def test_a_validation_error_is_described_by_its_masked_errors(self):
        described = describe_exception(_validation_error())

        assert described.startswith("ValidationError: ")
        assert "pin" in described
        assert PIN not in described

    @pytest.mark.parametrize(
        "exc",
        [
            _duplicate_key_error(),
            WriteError(f"dup key: {{ pin: \"{PIN}\" }}", 11000, {"code": 11000, "keyValue": {"pin": PIN}}),
            BulkWriteError({"writeErrors": [{"code": 11000, "errmsg": f"dup key: {PIN}", "keyValue": {"pin": PIN}}]}),
            OperationFailure(f"Write conflict on {{ pin: \"{PIN}\" }}", 112, {"code": 112, "codeName": "WriteConflict"}),
        ],
    )
    def test_a_driver_error_is_described_by_type_and_code_only(self, exc):
        described = describe_exception(exc)

        assert described.startswith(f"{type(exc).__name__}: code->")
        assert PIN not in described

    def test_the_code_name_is_kept(self):
        assert describe_exception(_duplicate_key_error()) == "DuplicateKeyError: code->11000, codeName->DuplicateKey"

    def test_any_other_exception_keeps_its_text(self):
        assert describe_exception(ValueError("cannot parse 'abc'")) == "ValueError: cannot parse 'abc'"

    def test_it_never_raises(self):
        class Broken(Exception):
            def __str__(self):
                raise RuntimeError("no text")

        assert describe_exception(Broken()) == "<undescribable Broken>"


@pytest.mark.parametrize("original", [_validation_error(), _duplicate_key_error()], ids=["pydantic", "pymongo"])
class TestAppExceptionKeepsTheOriginalOutOfTheResponse:
    def test_the_message_is_the_exceptions_own(self, original):
        exc = ServiceException("Failed to save staff", original_exception=original)

        assert exc.message == "Failed to save staff"
        assert PIN not in exc.log_message
        assert exc.log_message.startswith(f"Failed to save staff: {type(original).__name__}: ")

    def test_the_log_carries_the_description_not_the_values(self, original, caplog):
        with caplog.at_level(logging.ERROR):
            RepositoryException("Failed to save document", "staff", original_exception=original)

        logged = "\n".join(r.getMessage() for r in caplog.records)
        assert type(original).__name__ in logged
        assert PIN not in logged

    def test_the_response_and_its_log_line_leave_it_out(self, original, caplog):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise ServiceException("Failed to save staff", original_exception=original)

        with caplog.at_level(logging.DEBUG):
            response = TestClient(app).get("/boom")

        assert response.status_code == 500
        body = response.json()
        assert body["message"] == "Failed to save staff"
        assert PIN not in response.text
        assert PIN not in "\n".join(r.getMessage() for r in caplog.records)


def test_a_wrapped_app_exception_contributes_its_own_message():
    inner = ServiceException("Staff not found: staff_id->S1")
    outer = AppException("Sign-in failed", original_exception=inner)

    assert outer.message == "Sign-in failed"
    assert outer.log_message == "Sign-in failed: ServiceException: Staff not found: staff_id->S1"


# ---------------------------------------------------------------------------
# Review follow-ups (#318)
# ---------------------------------------------------------------------------


class TestMoreTypesAreSummarised:
    def test_fastapi_request_validation_errors_are_masked(self):
        from fastapi.exceptions import RequestValidationError

        exc = RequestValidationError([{"type": "string_type", "loc": ("body", "pin"), "msg": "bad", "input": int(PIN)}])

        described = describe_exception(exc)

        assert described.startswith("RequestValidationError: ")
        assert PIN not in described

    def test_pydantic_v1_validation_errors_are_masked(self):
        from pydantic.v1 import BaseModel as BaseModelV1, ValidationError as ValidationErrorV1

        class StaffV1(BaseModelV1):
            pin: int

        try:
            StaffV1(pin=f"x{PIN}")
        except ValidationErrorV1 as e:
            described = describe_exception(e)
        assert described.startswith("ValidationError: ")
        assert PIN not in described

    def test_a_bson_error_is_described_by_its_type(self):
        from bson.errors import InvalidDocument

        assert describe_exception(InvalidDocument(f"cannot encode object: {PIN}")) == "InvalidDocument"


class TestDescribeExceptionForResponse:
    def test_an_app_exception_keeps_its_own_message(self):
        from kugel_common.database.database_exceptions import DatabaseException
        from kugel_common.utils.log_utils import describe_exception_for_response

        exc = DatabaseException("Index tenant_id_1 on staff is not unique. Documents sharing this key: {'tenant_id': 'T1'} x2")

        assert describe_exception_for_response(exc) == f"DatabaseException: {exc}"

    def test_the_shared_app_exception_keeps_its_own_message(self):
        from kugel_common.utils.log_utils import describe_exception_for_response

        exc = ServiceException("Tenant setup failed", original_exception=_duplicate_key_error())

        assert describe_exception_for_response(exc) == "ServiceException: Tenant setup failed"

    def test_a_driver_error_is_summarised(self):
        from kugel_common.utils.log_utils import describe_exception_for_response

        assert describe_exception_for_response(_duplicate_key_error()) == "DuplicateKeyError: code->11000, codeName->DuplicateKey"

    def test_any_other_exception_gives_its_type_only(self):
        from kugel_common.utils.log_utils import describe_exception_for_response

        assert describe_exception_for_response(ValueError(f"pin={PIN}")) == "ValueError"


class TestUnhandledExceptions:
    def test_the_500_builder_returns_no_exception_text(self):
        from kugel_common.exceptions.exception_handlers import build_unexpected_error_response

        response = build_unexpected_error_response(_duplicate_key_error())

        assert response.data is None
        assert PIN not in str(response.model_dump())

    def test_a_raw_driver_error_escaping_an_endpoint_is_not_echoed(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise _duplicate_key_error()

        response = TestClient(app, raise_server_exceptions=False).get("/boom")

        assert response.status_code == 500
        assert PIN not in response.text
        assert response.json()["data"] is None


@pytest.mark.asyncio
async def test_a_slack_notification_describes_the_exception():
    import json
    from unittest.mock import AsyncMock, MagicMock, patch

    from kugel_common.utils import slack_notifier

    response = MagicMock(status=200)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.post = MagicMock(return_value=response)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
        with patch("aiohttp.ClientSession", return_value=session):
            await slack_notifier.send_fatal_error_notification(message="Failed to create log", error=_duplicate_key_error())

    body = session.post.call_args.kwargs["data"]
    assert PIN not in body
    details = next(f for f in json.loads(body)["attachments"][0]["fields"] if f["title"] == "Details")
    assert details["value"] == "DuplicateKeyError: code->11000, codeName->DuplicateKey"


# ---------------------------------------------------------------------------
# Second review round (#318): anything bound for a response or another
# service names a non-application exception by its type only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_tenant_setup_steps_report_safe_reasons():
    from kugel_common.database.database import run_setup_steps_async
    from kugel_common.database.database_exceptions import DatabaseException

    blocking = "Index tenant_id_1 on staff is not unique. Documents sharing this key: {'tenant_id': 'T1'} x2"

    async def raw_driver_error(_):
        raise _duplicate_key_error()

    async def other_error(_):
        raise ValueError(f"bad api_key {PIN}")

    async def index_blocked(_):
        raise DatabaseException(blocking)

    with pytest.raises(DatabaseException) as exc_info:
        await run_setup_steps_async("T1", [raw_driver_error, other_error, index_blocked])

    reason = str(exc_info.value)
    assert PIN not in reason
    assert "raw_driver_error: DuplicateKeyError: code->11000, codeName->DuplicateKey" in reason
    assert "other_error: ValueError" in reason
    assert blocking in reason, "the #185 detail is the application's own and is kept"


@pytest.mark.asyncio
async def test_a_health_check_names_a_failure_by_its_type():
    from unittest.mock import AsyncMock, MagicMock

    from kugel_common.utils.health_check import HealthChecker

    client = MagicMock()
    client.admin.command = AsyncMock(side_effect=RuntimeError(f"auth failed for password {PIN}"))

    health = await HealthChecker.check_mongodb(client)

    assert health.error == "MongoDB error: RuntimeError"

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

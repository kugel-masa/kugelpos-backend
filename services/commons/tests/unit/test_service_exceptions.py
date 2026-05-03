# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.exceptions.service_exceptions."""
import pytest
from fastapi import status

from kugel_common.exceptions.base_exceptions import ServiceException
from kugel_common.exceptions.error_codes import ErrorCode
from kugel_common.exceptions.service_exceptions import (
    BadRequestBodyException,
    DocumentAlreadyExistsException,
    DocumentNotFoundException,
    EventBadSequenceException,
    InvalidRequestDataException,
    StrategyPluginException,
)


class TestDocumentNotFoundException:
    def test_inherits_from_service_exception(self):
        exc = DocumentNotFoundException("not found")
        assert isinstance(exc, ServiceException)

    def test_status_404(self):
        exc = DocumentNotFoundException("not found")
        assert exc.status_code == status.HTTP_404_NOT_FOUND

    def test_carries_resource_not_found_code(self):
        exc = DocumentNotFoundException("not found")
        assert exc.error_code == ErrorCode.RESOURCE_NOT_FOUND


class TestDocumentAlreadyExistsException:
    def test_status_400(self):
        exc = DocumentAlreadyExistsException("dup")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_duplicate_key_code(self):
        exc = DocumentAlreadyExistsException("dup")
        assert exc.error_code == ErrorCode.DUPLICATE_KEY


class TestBadRequestBodyException:
    def test_status_400(self):
        exc = BadRequestBodyException("malformed")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_validation_error_code(self):
        exc = BadRequestBodyException("malformed")
        assert exc.error_code == ErrorCode.VALIDATION_ERROR


class TestInvalidRequestDataException:
    def test_status_422(self):
        exc = InvalidRequestDataException("bad data")
        # Either 422 constant works depending on FastAPI version
        assert exc.status_code in (
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            422,
        )

    def test_carries_validation_error_code(self):
        exc = InvalidRequestDataException("bad data")
        assert exc.error_code == ErrorCode.VALIDATION_ERROR


class TestEventBadSequenceException:
    def test_status_400(self):
        exc = EventBadSequenceException("out of order")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_invalid_operation_code(self):
        exc = EventBadSequenceException("out of order")
        assert exc.error_code == ErrorCode.INVALID_OPERATION


class TestStrategyPluginException:
    def test_status_500(self):
        exc = StrategyPluginException("plugin crashed")
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_carries_system_error_code(self):
        exc = StrategyPluginException("plugin crashed")
        assert exc.error_code == ErrorCode.SYSTEM_ERROR


class TestExceptionHierarchy:
    """Verify that all service-layer exceptions can be caught as ServiceException."""

    @pytest.mark.parametrize(
        "exc_factory",
        [
            lambda: DocumentNotFoundException("x"),
            lambda: DocumentAlreadyExistsException("x"),
            lambda: BadRequestBodyException("x"),
            lambda: InvalidRequestDataException("x"),
            lambda: EventBadSequenceException("x"),
            lambda: StrategyPluginException("x"),
        ],
    )
    def test_caught_as_service_exception(self, exc_factory):
        try:
            raise exc_factory()
        except ServiceException:
            pass
        else:
            pytest.fail("did not catch as ServiceException")

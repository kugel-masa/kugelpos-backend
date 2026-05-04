# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.api_exception_handler."""
import pytest
from fastapi import status

from kugel_common.exceptions.base_exceptions import AppException
from kugel_common.exceptions.error_codes import ErrorCode
from kugel_common.utils.api_exception_handler import (
    create_error_response,
    get_error_code_from_status,
)


class TestGetErrorCodeFromStatus:
    @pytest.mark.parametrize(
        ("http_status", "expected_code"),
        [
            (status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR),
            (status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTHENTICATION_ERROR),
            (status.HTTP_403_FORBIDDEN, ErrorCode.AUTHORIZATION_ERROR),
            (status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND),
            (status.HTTP_409_CONFLICT, ErrorCode.DUPLICATE_KEY),
            (status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.SYSTEM_ERROR),
        ],
    )
    def test_known_status_maps_to_expected_code(self, http_status, expected_code):
        assert get_error_code_from_status(http_status) == expected_code

    def test_422_maps_to_validation_error(self):
        # 422 has two spellings depending on FastAPI version; both should
        # land on VALIDATION_ERROR
        from fastapi import status as st

        candidates = [
            getattr(st, "HTTP_422_UNPROCESSABLE_ENTITY", None),
            getattr(st, "HTTP_422_UNPROCESSABLE_CONTENT", None),
            422,
        ]
        for code in [c for c in candidates if c is not None]:
            assert get_error_code_from_status(code) == ErrorCode.VALIDATION_ERROR

    def test_unknown_status_falls_back_to_unexpected(self):
        assert get_error_code_from_status(599) == ErrorCode.UNEXPECTED_ERROR


class TestCreateErrorResponse:
    def test_uses_app_exception_user_error(self):
        exc = AppException(
            "internal",
            error_code="100001",
            user_message="ユーザー向けメッセージ",
        )
        resp = create_error_response(404, "internal detail", exc=exc)
        assert resp.success is False
        assert resp.code == 404
        assert resp.user_error.code == "100001"
        assert resp.user_error.message == "ユーザー向けメッセージ"

    def test_default_user_error_for_status(self):
        resp = create_error_response(404, "not found")
        assert resp.user_error.code == ErrorCode.RESOURCE_NOT_FOUND
        # message comes from ErrorMessage lookup
        assert resp.user_error.message  # non-empty

    def test_internal_message_preserves_detail_when_no_exception(self):
        resp = create_error_response(500, "internal failure")
        assert resp.message == "internal failure"

    def test_internal_message_uses_str_exception_when_provided(self):
        exc = AppException("wrapped boom")
        resp = create_error_response(500, "ignored detail", exc=exc)
        # internal_message becomes str(exc), which includes the message
        assert "wrapped boom" in resp.message

    def test_unknown_status_uses_unexpected_error(self):
        resp = create_error_response(599, "weird")
        assert resp.user_error.code == ErrorCode.UNEXPECTED_ERROR

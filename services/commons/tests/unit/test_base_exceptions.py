# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.exceptions.base_exceptions."""
import logging

import pytest

from kugel_common.exceptions.base_exceptions import (
    AppException,
    DatabaseException,
    RepositoryException,
    ServiceException,
)
from kugel_common.exceptions.error_codes import ErrorCode, ErrorMessage


class TestAppException:
    def test_basic_construction(self):
        exc = AppException("something failed")
        assert str(exc) == "something failed"
        assert exc.error_code is None
        assert exc.user_message is None
        assert exc.status_code == 500

    def test_full_construction(self):
        original = ValueError("inner")
        exc = AppException(
            "wrapped",
            original_exception=original,
            error_code="100001",
            user_message="ユーザー向けメッセージ",
            status_code=404,
        )
        assert exc.error_code == "100001"
        assert exc.user_message == "ユーザー向けメッセージ"
        assert exc.status_code == 404
        assert exc.original_exception is original
        # message field appends original exception text
        assert "wrapped" in exc.message
        assert "inner" in exc.message

    def test_logs_via_provided_logger(self, caplog):
        custom_logger = logging.getLogger("test.custom")
        with caplog.at_level(logging.ERROR, logger="test.custom"):
            AppException("logged message", logger=custom_logger)
        assert any("logged message" in r.message for r in caplog.records)

    def test_log_level_warning(self, caplog):
        custom_logger = logging.getLogger("test.warn")
        with caplog.at_level(logging.WARNING, logger="test.warn"):
            AppException("warn msg", logger=custom_logger, log_level=logging.WARNING)
        # Ensure record was at WARNING level
        warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("warn msg" in r.message for r in warn_records)

    def test_get_user_error_with_explicit_code(self):
        exc = AppException(
            "x",
            error_code="100001",
            user_message="custom msg",
        )
        result = exc.get_user_error()
        assert result == {"code": "100001", "message": "custom msg"}

    def test_get_user_error_falls_back_to_system_error(self):
        exc = AppException("x")
        result = exc.get_user_error()
        assert result["code"] == ErrorCode.SYSTEM_ERROR
        assert result["message"] == ErrorMessage.get_message(ErrorCode.SYSTEM_ERROR)


class TestDatabaseException:
    def test_inherits_from_app_exception(self):
        exc = DatabaseException("db failed")
        assert isinstance(exc, AppException)
        assert exc.status_code == 500

    def test_custom_status_code(self):
        exc = DatabaseException("conn lost", status_code=503)
        assert exc.status_code == 503


class TestRepositoryException:
    def test_inherits_from_app_exception(self):
        exc = RepositoryException("repo fail", collection_name="users")
        assert isinstance(exc, AppException)

    def test_message_includes_collection_name(self):
        exc = RepositoryException("repo fail", collection_name="users")
        assert "users" in exc.message

    def test_default_status_code_is_404(self):
        exc = RepositoryException("repo fail", collection_name="users")
        assert exc.status_code == 404

    def test_passes_through_error_code_and_user_message(self):
        exc = RepositoryException(
            "repo fail",
            collection_name="users",
            error_code="500001",
            user_message="DB error",
        )
        assert exc.error_code == "500001"
        assert exc.user_message == "DB error"


class TestServiceException:
    def test_inherits_from_app_exception(self):
        exc = ServiceException("svc fail")
        assert isinstance(exc, AppException)
        assert exc.status_code == 500

    def test_log_level_can_be_warning(self, caplog):
        custom_logger = logging.getLogger("test.svc")
        with caplog.at_level(logging.WARNING, logger="test.svc"):
            ServiceException("svc warn", logger=custom_logger, log_level=logging.WARNING)
        assert any("svc warn" in r.message for r in caplog.records)

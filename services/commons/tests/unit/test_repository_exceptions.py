# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.exceptions.repository_exceptions."""
import pytest
from fastapi import status

from kugel_common.exceptions.base_exceptions import RepositoryException
from kugel_common.exceptions.error_codes import ErrorCode
from kugel_common.exceptions.repository_exceptions import (
    AlreadyExistException,
    CannotCreateException,
    CannotDeleteException,
    DeleteChildExistException,
    DuplicateKeyException,
    LoadDataNoExistException,
    NotFoundException,
    ReplaceNotWorkException,
    UpdateNotWorkException,
)


class TestNotFoundException:
    def test_inherits_from_repository_exception(self):
        exc = NotFoundException("nope", collection_name="users", find_key="user-1")
        assert isinstance(exc, RepositoryException)

    def test_status_code_is_404(self):
        exc = NotFoundException("nope", collection_name="users", find_key="user-1")
        assert exc.status_code == status.HTTP_404_NOT_FOUND

    def test_carries_resource_not_found_error_code(self):
        exc = NotFoundException("nope", collection_name="users", find_key="user-1")
        assert exc.error_code == ErrorCode.RESOURCE_NOT_FOUND

    def test_message_includes_find_key_and_collection(self):
        exc = NotFoundException("nope", collection_name="users", find_key="user-42")
        assert "user-42" in exc.message
        assert "users" in exc.message


class TestCannotCreateException:
    def test_status_400(self):
        exc = CannotCreateException("fail", collection_name="users", document={"x": 1})
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_cannot_create_code(self):
        exc = CannotCreateException("fail", collection_name="users", document={"x": 1})
        assert exc.error_code == ErrorCode.CANNOT_CREATE

    def test_message_includes_document_repr(self):
        exc = CannotCreateException("fail", collection_name="users", document={"x": 1})
        assert "x" in exc.message  # dict repr leaks the key


class TestCannotDeleteException:
    def test_status_400(self):
        exc = CannotDeleteException("fail", collection_name="users", delete_key="u1")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_cannot_delete_code(self):
        exc = CannotDeleteException("fail", collection_name="users", delete_key="u1")
        assert exc.error_code == ErrorCode.CANNOT_DELETE

    def test_message_includes_delete_key(self):
        exc = CannotDeleteException("fail", collection_name="users", delete_key="u-key-7")
        assert "u-key-7" in exc.message


class TestUpdateNotWorkException:
    def test_status_400(self):
        exc = UpdateNotWorkException("fail", collection_name="users", update_key="u1")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_update_not_work_code(self):
        exc = UpdateNotWorkException("fail", collection_name="users", update_key="u1")
        assert exc.error_code == ErrorCode.UPDATE_NOT_WORK


class TestReplaceNotWorkException:
    def test_status_400(self):
        exc = ReplaceNotWorkException("fail", collection_name="users", update_key="u1")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_replace_not_work_code(self):
        exc = ReplaceNotWorkException("fail", collection_name="users", update_key="u1")
        assert exc.error_code == ErrorCode.REPLACE_NOT_WORK


class TestDeleteChildExistException:
    def test_status_400(self):
        exc = DeleteChildExistException("fail", collection_name="parent", delete_key="p1")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_delete_child_exist_code(self):
        exc = DeleteChildExistException("fail", collection_name="parent", delete_key="p1")
        assert exc.error_code == ErrorCode.DELETE_CHILD_EXIST


class TestAlreadyExistException:
    def test_status_400(self):
        exc = AlreadyExistException("dup", collection_name="users", find_key="u1")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_duplicate_key_code(self):
        exc = AlreadyExistException("dup", collection_name="users", find_key="u1")
        assert exc.error_code == ErrorCode.DUPLICATE_KEY


class TestDuplicateKeyException:
    def test_status_400(self):
        exc = DuplicateKeyException("dup", collection_name="users", key="email")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_carries_duplicate_key_code(self):
        exc = DuplicateKeyException("dup", collection_name="users", key="email")
        assert exc.error_code == ErrorCode.DUPLICATE_KEY

    def test_message_includes_key(self):
        exc = DuplicateKeyException("dup", collection_name="users", key="unique-email")
        assert "unique-email" in exc.message


class TestLoadDataNoExistException:
    def test_status_404(self):
        exc = LoadDataNoExistException("missing", data_name="config.yaml")
        assert exc.status_code == status.HTTP_404_NOT_FOUND

    def test_uses_load_data_collection_name(self):
        exc = LoadDataNoExistException("missing", data_name="config.yaml")
        assert "load_data" in exc.message

    def test_message_includes_data_name(self):
        exc = LoadDataNoExistException("missing", data_name="config.yaml")
        assert "config.yaml" in exc.message

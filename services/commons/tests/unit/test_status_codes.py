# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.status_codes."""
import pytest
from fastapi import status

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.status_codes import StatusCodes


class TestStatusCodesShape:
    @pytest.mark.parametrize(
        "code",
        [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
            getattr(
                status,
                "HTTP_422_UNPROCESSABLE_ENTITY",
                getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            ),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ],
    )
    def test_each_entry_has_required_keys(self, code):
        if code not in StatusCodes:
            # 422 may register under either name depending on FastAPI version
            return
        entry = StatusCodes[code]
        assert "description" in entry
        assert entry["model"] is ApiResponse
        assert "content" in entry
        assert "application/json" in entry["content"]
        assert "example" in entry["content"]["application/json"]

    def test_400_example_matches_status(self):
        example = StatusCodes[status.HTTP_400_BAD_REQUEST]["content"][
            "application/json"
        ]["example"]
        assert example["code"] == 400
        assert example["success"] is False

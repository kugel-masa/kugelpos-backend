# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.schemas package."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from kugel_common.schemas.api_response import ApiResponse, UserError
from kugel_common.schemas.base_schemas import BaseSchemmaModel, Metadata
from kugel_common.schemas.health import (
    ComponentHealth,
    HealthCheckResponse,
    HealthStatus,
)
from kugel_common.schemas.pagination import PaginatedResult


# ---------------------------------------------------------------------------
# base_schemas
# ---------------------------------------------------------------------------

class TestBaseSchemmaModel:
    def test_alias_generator_camel_case(self):
        class Sample(BaseSchemmaModel):
            user_name: str
            email_address: str

        s = Sample(user_name="alice", email_address="a@example.com")
        dumped = s.model_dump(by_alias=True)
        assert dumped == {"userName": "alice", "emailAddress": "a@example.com"}

    def test_populate_by_name_accepts_snake_case_input(self):
        class Sample(BaseSchemmaModel):
            user_name: str

        s = Sample(user_name="alice")
        assert s.user_name == "alice"

    def test_populate_by_name_accepts_camel_case_input(self):
        class Sample(BaseSchemmaModel):
            user_name: str

        # When populate_by_name=True, both alias (camelCase) and field name work
        s = Sample(userName="alice")
        assert s.user_name == "alice"


class TestMetadata:
    def test_required_fields(self):
        m = Metadata(total=100, page=2, limit=20, sort="name:1", filter={"active": True})
        assert m.total == 100
        assert m.page == 2
        assert m.limit == 20

    def test_optional_sort_and_filter(self):
        m = Metadata(total=10, page=1, limit=10, sort=None, filter=None)
        assert m.sort is None
        assert m.filter is None

    def test_dump_camel_case(self):
        m = Metadata(total=5, page=1, limit=10, sort=None, filter=None)
        dumped = m.model_dump(by_alias=True)
        # All fields are single-word so camelCase == snake_case here
        assert dumped["total"] == 5


# ---------------------------------------------------------------------------
# api_response
# ---------------------------------------------------------------------------

class TestUserError:
    def test_optional_fields_default_none(self):
        ue = UserError()
        assert ue.code is None
        assert ue.message is None

    def test_explicit_values(self):
        ue = UserError(code="100001", message="error message")
        assert ue.code == "100001"
        assert ue.message == "error message"


class TestApiResponse:
    def test_default_code_is_200(self):
        r = ApiResponse(success=True, message="ok", data={"x": 1})
        assert r.code == 200
        assert r.success is True

    def test_explicit_code(self):
        r = ApiResponse(success=False, code=500, message="err", data=None)
        assert r.code == 500

    def test_user_error_passes_through(self):
        ue = UserError(code="100001", message="err")
        r = ApiResponse(
            success=False,
            code=400,
            message="bad",
            data=None,
            user_error=ue,
        )
        assert r.user_error.code == "100001"

    def test_metadata_optional(self):
        r = ApiResponse(success=True, message="ok", data=[])
        assert r.metadata is None

    def test_with_metadata(self):
        meta = Metadata(total=5, page=1, limit=10, sort=None, filter=None)
        r = ApiResponse(success=True, message="ok", data=[], metadata=meta)
        assert r.metadata.total == 5

    def test_camel_case_serialization(self):
        ue = UserError(code="X", message="Y")
        r = ApiResponse(
            success=True,
            message="ok",
            data=None,
            user_error=ue,
            operation="create_user",
        )
        d = r.model_dump(by_alias=True)
        # `user_error` field becomes `userError`
        assert "userError" in d
        # `operation` is single-word
        assert d.get("operation") == "create_user"

    def test_generic_data_type(self):
        # ApiResponse[T] is generic; data can be any type
        r: ApiResponse[dict] = ApiResponse(success=True, message="ok", data={"a": 1})
        assert r.data == {"a": 1}


# ---------------------------------------------------------------------------
# pagination
# ---------------------------------------------------------------------------

class TestPaginatedResult:
    def test_basic_construction(self):
        meta = Metadata(total=2, page=1, limit=10, sort=None, filter=None)
        r = PaginatedResult[dict](data=[{"a": 1}, {"a": 2}], metadata=meta)
        assert len(r.data) == 2
        assert r.metadata.total == 2

    def test_camel_case_serialization(self):
        meta = Metadata(total=0, page=1, limit=10, sort=None, filter=None)
        r = PaginatedResult[dict](data=[], metadata=meta)
        d = r.model_dump(by_alias=True)
        assert "data" in d
        assert "metadata" in d


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

class TestHealthStatusEnum:
    def test_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_string_inheritance(self):
        # HealthStatus inherits from str, useful for JSON serialization
        assert HealthStatus.HEALTHY == "healthy"


class TestComponentHealth:
    def test_minimal(self):
        c = ComponentHealth(status=HealthStatus.HEALTHY)
        assert c.status == HealthStatus.HEALTHY
        assert c.response_time_ms is None
        assert c.details is None
        assert c.error is None
        assert c.component is None

    def test_full(self):
        c = ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            response_time_ms=123,
            details={"foo": "bar"},
            error="connection refused",
            component="mongodb",
        )
        assert c.response_time_ms == 123
        assert c.details == {"foo": "bar"}
        assert c.error == "connection refused"
        assert c.component == "mongodb"

    def test_status_required(self):
        with pytest.raises(ValidationError):
            ComponentHealth()


class TestHealthCheckResponse:
    def test_minimal(self):
        r = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            service="cart",
            version="1.0.0",
        )
        assert r.service == "cart"
        assert r.version == "1.0.0"
        assert isinstance(r.timestamp, datetime)
        assert r.checks == {}

    def test_with_checks(self):
        r = HealthCheckResponse(
            status=HealthStatus.UNHEALTHY,
            service="cart",
            version="1.0.0",
            checks={
                "mongodb": ComponentHealth(status=HealthStatus.HEALTHY, response_time_ms=2),
                "dapr_sidecar": ComponentHealth(
                    status=HealthStatus.UNHEALTHY, error="timeout"
                ),
            },
        )
        assert r.checks["mongodb"].status == HealthStatus.HEALTHY
        assert r.checks["dapr_sidecar"].error == "timeout"

    def test_timestamp_serialized_with_z_suffix(self):
        r = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            service="x",
            version="1",
        )
        d = r.model_dump()
        # Custom serializer appends "Z" to ISO timestamp
        assert isinstance(d["timestamp"], str)
        assert d["timestamp"].endswith("Z")

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            HealthCheckResponse(status=HealthStatus.HEALTHY, service="x")  # missing version

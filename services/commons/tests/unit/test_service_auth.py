# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.service_auth.create_service_token."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from kugel_common.config.settings import settings
from kugel_common.utils.service_auth import create_service_token


class TestCreateServiceToken:
    def _decode(self, token: str) -> dict:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    def test_basic_claims(self):
        token = create_service_token(tenant_id="T001", service_name="report-service")
        claims = self._decode(token)
        assert claims["sub"] == "service:report-service"
        assert claims["tenant_id"] == "T001"
        assert claims["service"] == "report-service"
        assert claims["is_service_account"] is True
        assert claims["is_superuser"] is False
        assert "exp" in claims

    def test_default_expiry_is_around_five_minutes(self):
        before = datetime.now(timezone.utc)
        token = create_service_token(tenant_id="T001", service_name="x")
        claims = self._decode(token)
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        delta = (exp - before).total_seconds()
        # Allow ±10s slack for clock + execution
        assert 290 <= delta <= 310

    def test_custom_expires_delta_overrides_default(self):
        before = datetime.now(timezone.utc)
        token = create_service_token(
            tenant_id="T001",
            service_name="x",
            expires_delta=timedelta(hours=2),
        )
        claims = self._decode(token)
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        delta = (exp - before).total_seconds()
        # ~2 hours
        assert 7195 <= delta <= 7210

    def test_token_signed_with_settings_secret(self):
        token = create_service_token(tenant_id="T001", service_name="x")
        # Should decode cleanly with the configured secret
        claims = self._decode(token)
        assert claims["tenant_id"] == "T001"

        # Should fail with a wrong secret
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "different-secret-1234567890abcdef", algorithms=[settings.ALGORITHM])

    def test_different_service_names_yield_different_subjects(self):
        t1 = create_service_token(tenant_id="T001", service_name="report-service")
        t2 = create_service_token(tenant_id="T001", service_name="cart-service")
        c1 = self._decode(t1)
        c2 = self._decode(t2)
        assert c1["sub"] != c2["sub"]
        assert c1["service"] == "report-service"
        assert c2["service"] == "cart-service"

    def test_different_tenants_isolated(self):
        t1 = create_service_token(tenant_id="A", service_name="x")
        t2 = create_service_token(tenant_id="B", service_name="x")
        assert self._decode(t1)["tenant_id"] == "A"
        assert self._decode(t2)["tenant_id"] == "B"

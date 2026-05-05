# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.security."""
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import HTTPException

from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.security import (
    get_current_user,
    get_service_account_info,
    get_tenant_id,
    get_terminal_info_from_terminal_service,
    terminal_claims_to_terminal_info,
    transform_terminal_info,
    verify_pubsub_notification_auth,
    verify_tenant_id,
    verify_terminal_token,
    verify_token,
)


def _user_token(
    sub: str = "alice",
    tenant_id: str = "T001",
    is_superuser: bool = False,
    is_service_account: bool = False,
    service: str = None,
    extra: dict = None,
) -> str:
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "is_superuser": is_superuser,
        "is_service_account": is_service_account,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if service is not None:
        payload["service"] = service
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _terminal_token(
    tenant_id: str = "T001",
    store_code: str = "001",
    terminal_no: int = 1,
    terminal_id: str = "T001-001-01",
    status_value: str = "Idle",
    business_date: str = None,
    open_counter: int = None,
    business_counter: int = None,
    staff_id: str = None,
    staff_name: str = None,
    token_type: str = "terminal",
) -> str:
    payload = {
        "sub": f"terminal:{terminal_id}",
        "tenant_id": tenant_id,
        "store_code": store_code,
        "terminal_no": terminal_no,
        "terminal_id": terminal_id,
        "status": status_value,
        "token_type": token_type,
        "iss": "terminal-service",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if business_date is not None:
        payload["business_date"] = business_date
    if open_counter is not None:
        payload["open_counter"] = open_counter
    if business_counter is not None:
        payload["business_counter"] = business_counter
    if staff_id is not None:
        payload["staff_id"] = staff_id
        payload["staff_name"] = staff_name
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ---------------------------------------------------------------------------
# verify_token
# ---------------------------------------------------------------------------

class TestVerifyToken:
    def test_valid_token_returns_user_dict(self):
        token = _user_token(sub="alice", tenant_id="T001")
        result = verify_token(token)
        assert result["username"] == "alice"
        assert result["tenant_id"] == "T001"
        assert result["is_superuser"] is False
        assert result["is_service_account"] is False
        assert result["service"] is None

    def test_superuser_flag_passed_through(self):
        token = _user_token(is_superuser=True)
        assert verify_token(token)["is_superuser"] is True

    def test_service_account_flag_passed_through(self):
        token = _user_token(is_service_account=True, service="report-service")
        info = verify_token(token)
        assert info["is_service_account"] is True
        assert info["service"] == "report-service"

    def test_missing_sub_raises_401(self):
        payload = {
            "tenant_id": "T001",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            verify_token(token)
        assert exc.value.status_code == 401

    def test_missing_tenant_id_raises_401(self):
        payload = {
            "sub": "alice",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            verify_token(token)
        assert exc.value.status_code == 401

    def test_invalid_jwt_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            verify_token("not.a.valid.jwt")
        assert exc.value.status_code == 401

    def test_wrong_secret_signature_raises_401(self):
        payload = {
            "sub": "alice",
            "tenant_id": "T001",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, "different-secret-1234567890abcd", algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException):
            verify_token(token)

    def test_expired_token_raises_401(self):
        payload = {
            "sub": "alice",
            "tenant_id": "T001",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException):
            verify_token(token)


# ---------------------------------------------------------------------------
# verify_tenant_id
# ---------------------------------------------------------------------------

class TestVerifyTenantId:
    def test_matching_does_not_raise(self):
        verify_tenant_id("T001", "T001", logging.getLogger("test"))

    def test_mismatch_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            verify_tenant_id("T001", "T999", logging.getLogger("test"))
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# verify_terminal_token
# ---------------------------------------------------------------------------

class TestVerifyTerminalToken:
    def test_valid_terminal_token(self):
        token = _terminal_token(tenant_id="T001", terminal_id="T001-001-01")
        claims = verify_terminal_token(token)
        assert claims["tenant_id"] == "T001"
        assert claims["terminal_id"] == "T001-001-01"
        assert claims["token_type"] == "terminal"

    def test_wrong_token_type_raises_401(self):
        token = _terminal_token(token_type="user")
        with pytest.raises(HTTPException) as exc:
            verify_terminal_token(token)
        assert exc.value.status_code == 401

    def test_missing_tenant_id_raises_401(self):
        # Manually craft a terminal token without tenant_id
        payload = {
            "sub": "terminal:T001-001-01",
            "token_type": "terminal",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException):
            verify_terminal_token(token)

    def test_invalid_jwt_raises_401(self):
        with pytest.raises(HTTPException):
            verify_terminal_token("garbage")


# ---------------------------------------------------------------------------
# terminal_claims_to_terminal_info
# ---------------------------------------------------------------------------

class TestTerminalClaimsToTerminalInfo:
    def test_basic_fields(self):
        claims = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 5,
            "terminal_id": "T001-001-05",
            "status": "Idle",
        }
        info = terminal_claims_to_terminal_info(claims)
        assert info.tenant_id == "T001"
        assert info.terminal_id == "T001-001-05"
        assert info.status == "Idle"

    def test_optional_business_fields(self):
        claims = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "status": "Opened",
            "business_date": "20260101",
            "open_counter": 3,
            "business_counter": 4,
        }
        info = terminal_claims_to_terminal_info(claims)
        assert info.business_date == "20260101"
        assert info.open_counter == 3
        assert info.business_counter == 4

    def test_staff_populated_when_present(self):
        claims = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "status": "Idle",
            "staff_id": "S001",
            "staff_name": "Alice",
        }
        info = terminal_claims_to_terminal_info(claims)
        assert info.staff is not None
        assert info.staff.id == "S001"
        assert info.staff.name == "Alice"

    def test_staff_omitted_when_no_staff_id(self):
        claims = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "status": "Idle",
        }
        info = terminal_claims_to_terminal_info(claims)
        assert info.staff is None


# ---------------------------------------------------------------------------
# get_tenant_id (terminal-id parser)
# ---------------------------------------------------------------------------

class TestGetTenantIdFromTerminalId:
    def test_three_part_terminal_id(self):
        assert get_tenant_id("T001-S5678-99") == "T001"

    def test_simple_terminal_id(self):
        assert get_tenant_id("ABC-X-1") == "ABC"

    def test_no_separator_returns_full_string(self):
        assert get_tenant_id("noseparator") == "noseparator"


# ---------------------------------------------------------------------------
# transform_terminal_info
# ---------------------------------------------------------------------------

class TestTransformTerminalInfo:
    def test_minimal_dict(self):
        d = {"tenant_id": "T001", "store_code": "001", "terminal_no": 1, "terminal_id": "T001-001-01"}
        info = transform_terminal_info(d)
        assert isinstance(info, TerminalInfoDocument)
        assert info.staff is None

    def test_staff_camel_case(self):
        d = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "staff": {"staffId": "S1", "staffName": "Alice", "staffPin": "1234"},
        }
        info = transform_terminal_info(d)
        assert info.staff is not None
        assert info.staff.id == "S1"
        assert info.staff.name == "Alice"
        assert info.staff.pin == "1234"

    def test_staff_snake_case(self):
        d = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "staff": {"id": "S2", "name": "Bob", "pin": "9999"},
        }
        info = transform_terminal_info(d)
        assert info.staff.id == "S2"
        assert info.staff.name == "Bob"
        assert info.staff.pin == "9999"


# ---------------------------------------------------------------------------
# get_terminal_info_from_terminal_service
# ---------------------------------------------------------------------------

class TestGetTerminalInfoFromTerminalService:
    """The terminal endpoint masks api_key in responses to X-API-KEY auth.
    Cart/master-data/etc. cache this TerminalInfoDocument and re-use api_key
    to call further services, so the helper must restore the caller-supplied
    api_key on the returned doc. Regression guard for the prod fix that
    landed alongside DISABLE_API_KEY_MASKING removal.
    """

    @pytest.mark.asyncio
    async def test_response_masked_api_key_overwritten_with_caller_api_key(self):
        """Even if the terminal API responds with a masked api_key, the helper
        must return a doc carrying the original (caller-supplied) api_key."""
        masked_response = {
            "data": {
                "tenant_id": "T001",
                "store_code": "001",
                "terminal_no": 1,
                "terminal_id": "T001-001-01",
                "api_key": "abcd...wxyz",  # masked by the terminal service
            }
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=masked_response)

        with patch(
            "kugel_common.security.get_pooled_client",
            new=AsyncMock(return_value=mock_client),
        ):
            result = await get_terminal_info_from_terminal_service(
                "T001-001-01", "real-unmasked-api-key-1234"
            )

        assert result.api_key == "real-unmasked-api-key-1234"

    @pytest.mark.asyncio
    async def test_unmasked_response_still_uses_caller_api_key(self):
        """Even when response already has the unmasked key (e.g. dev/test),
        we still authoritatively restore the caller-supplied api_key. This
        guards against subtle drift if response semantics change later."""
        unmasked_response = {
            "data": {
                "tenant_id": "T001",
                "store_code": "001",
                "terminal_no": 1,
                "terminal_id": "T001-001-01",
                "api_key": "something-else-server-side",
            }
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=unmasked_response)

        with patch(
            "kugel_common.security.get_pooled_client",
            new=AsyncMock(return_value=mock_client),
        ):
            result = await get_terminal_info_from_terminal_service(
                "T001-001-01", "real-unmasked-api-key-1234"
            )

        # Caller-supplied wins, period.
        assert result.api_key == "real-unmasked-api-key-1234"


# ---------------------------------------------------------------------------
# get_current_user / get_service_account_info
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_delegates_to_verify_token(self):
        token = _user_token(sub="alice")
        result = await get_current_user(token)
        assert result["username"] == "alice"


class TestGetServiceAccountInfo:
    @pytest.mark.asyncio
    async def test_service_account_returns_user_info(self):
        token = _user_token(is_service_account=True, service="report-service")
        result = await get_service_account_info(token)
        assert result["is_service_account"] is True
        assert result["service"] == "report-service"

    @pytest.mark.asyncio
    async def test_non_service_account_raises_403(self):
        token = _user_token(is_service_account=False)
        with pytest.raises(HTTPException) as exc:
            await get_service_account_info(token)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# verify_pubsub_notification_auth
# ---------------------------------------------------------------------------

class TestVerifyPubsubNotificationAuth:
    @pytest.mark.asyncio
    async def test_service_jwt_accepted(self):
        token = _user_token(is_service_account=True, service="report-service")
        result = await verify_pubsub_notification_auth(api_key=None, token=token)
        assert result["auth_type"] == "jwt"
        assert result["service"] == "report-service"

    @pytest.mark.asyncio
    async def test_non_service_jwt_falls_through_and_fails_without_api_key(self):
        # Regular user token isn't a service account; falls through to api-key check
        token = _user_token(is_service_account=False)
        with pytest.raises(HTTPException) as exc:
            await verify_pubsub_notification_auth(api_key=None, token=token)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_accepted(self):
        result = await verify_pubsub_notification_auth(
            api_key=settings.PUBSUB_NOTIFY_API_KEY,
            token=None,
        )
        assert result["auth_type"] == "api_key"
        assert result["service"] is None
        assert result["tenant_id"] is None

    @pytest.mark.asyncio
    async def test_no_credentials_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await verify_pubsub_notification_auth(api_key=None, token=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_api_key_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await verify_pubsub_notification_auth(api_key="bogus-key", token=None)
        assert exc.value.status_code == 401

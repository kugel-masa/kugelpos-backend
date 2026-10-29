"""
Unit tests for terminal JWT token generation and verification.
"""
import pytest
from datetime import timedelta
import jwt

from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.utils.terminal_auth import create_terminal_token
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from kugel_common.security import (
    get_tenant_id_with_security,
    get_tenant_id_with_security_by_query,
    get_tenant_id_with_security_by_query_optional,
    terminal_claims_to_terminal_info,
    verify_path_binding,
    verify_terminal_binding,
    verify_terminal_token,
)


def _make_terminal_info(
    tenant_id="T001",
    store_code="001",
    terminal_no=1,
    status="Idle",
    staff_id=None,
    staff_name=None,
    business_date=None,
    open_counter=None,
    business_counter=None,
) -> TerminalInfoDocument:
    """Helper to create a TerminalInfoDocument for testing."""
    terminal_id = f"{tenant_id}-{store_code}-{terminal_no:02d}"
    info = TerminalInfoDocument(
        tenant_id=tenant_id,
        store_code=store_code,
        terminal_no=terminal_no,
        terminal_id=terminal_id,
        status=status,
        business_date=business_date,
        open_counter=open_counter,
        business_counter=business_counter,
    )
    if staff_id:
        info.staff = StaffMasterDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            id=staff_id,
            name=staff_name,
        )
    return info


class TestCreateTerminalToken:
    """Tests for create_terminal_token()."""

    def test_basic_token_generation(self):
        """Valid TerminalInfoDocument produces a decodable JWT with correct claims."""
        info = _make_terminal_info()
        token = create_terminal_token(info)

        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["sub"] == "terminal:T001-001-01"
        assert claims["tenant_id"] == "T001"
        assert claims["store_code"] == "001"
        assert claims["terminal_no"] == 1
        assert claims["terminal_id"] == "T001-001-01"
        assert claims["status"] == "Idle"
        assert claims["token_type"] == "terminal"
        assert claims["iss"] == "terminal-service"
        assert "iat" in claims
        assert "exp" in claims

    def test_staff_claims_included_when_signed_in(self):
        """Staff claims are present when terminal has a signed-in staff."""
        info = _make_terminal_info(staff_id="S001", staff_name="Test Staff")
        token = create_terminal_token(info)

        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["staff_id"] == "S001"
        assert claims["staff_name"] == "Test Staff"

    def test_no_staff_claims_when_not_signed_in(self):
        """Staff claims are absent when no staff is signed in."""
        info = _make_terminal_info()
        token = create_terminal_token(info)

        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "staff_id" not in claims
        assert "staff_name" not in claims

    def test_opened_terminal_claims(self):
        """Opened terminal includes business_date, open_counter, business_counter."""
        info = _make_terminal_info(
            status="Opened",
            business_date="20260324",
            open_counter=5,
            business_counter=10,
        )
        token = create_terminal_token(info)

        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert claims["status"] == "Opened"
        assert claims["business_date"] == "20260324"
        assert claims["open_counter"] == 5
        assert claims["business_counter"] == 10

    def test_custom_expiry(self):
        """Custom expires_delta is respected."""
        info = _make_terminal_info()
        token = create_terminal_token(info, expires_delta=timedelta(hours=1))

        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in claims


class TestVerifyTerminalToken:
    """Tests for verify_terminal_token()."""

    def test_valid_token_returns_claims(self):
        """A valid terminal token is successfully verified."""
        info = _make_terminal_info(staff_id="S001", staff_name="Test Staff")
        token = create_terminal_token(info)

        claims = verify_terminal_token(token)
        assert claims["tenant_id"] == "T001"
        assert claims["token_type"] == "terminal"
        assert claims["staff_id"] == "S001"

    def test_expired_token_raises(self):
        """An expired token raises HTTPException."""
        from fastapi import HTTPException

        info = _make_terminal_info()
        token = create_terminal_token(info, expires_delta=timedelta(seconds=-1))

        with pytest.raises(HTTPException) as exc_info:
            verify_terminal_token(token)
        assert exc_info.value.status_code == 401

    def test_invalid_signature_raises(self):
        """A token signed with a wrong key raises HTTPException."""
        from fastapi import HTTPException

        info = _make_terminal_info()
        # Create token with a different key
        claims = {
            "sub": "terminal:T001-001-01",
            "tenant_id": "T001",
            "token_type": "terminal",
            "terminal_id": "T001-001-01",
        }
        bad_token = jwt.encode(claims, "wrong-secret-key", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            verify_terminal_token(bad_token)
        assert exc_info.value.status_code == 401

    def test_wrong_token_type_raises(self):
        """A token with token_type != 'terminal' raises HTTPException."""
        from fastapi import HTTPException

        # Create a user-type token
        claims = {
            "sub": "admin",
            "tenant_id": "T001",
            "token_type": "user",
        }
        user_token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_terminal_token(user_token)
        assert exc_info.value.status_code == 401

    def test_missing_tenant_id_raises(self):
        """A token without tenant_id raises HTTPException."""
        from fastapi import HTTPException

        claims = {
            "sub": "terminal:T001-001-01",
            "token_type": "terminal",
        }
        token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            verify_terminal_token(token)
        assert exc_info.value.status_code == 401


class TestTerminalClaimsToTerminalInfo:
    """Tests for terminal_claims_to_terminal_info()."""

    def test_basic_conversion(self):
        """Claims are correctly converted to TerminalInfoDocument."""
        claims = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "status": "Opened",
            "business_date": "20260324",
            "open_counter": 5,
            "business_counter": 10,
        }

        info = terminal_claims_to_terminal_info(claims)
        assert info.tenant_id == "T001"
        assert info.store_code == "001"
        assert info.terminal_no == 1
        assert info.terminal_id == "T001-001-01"
        assert info.status == "Opened"
        assert info.business_date == "20260324"
        assert info.open_counter == 5
        assert info.business_counter == 10
        assert info.staff is None

    def test_conversion_with_staff(self):
        """Claims with staff_id produce TerminalInfoDocument with staff."""
        claims = {
            "tenant_id": "T001",
            "store_code": "001",
            "terminal_no": 1,
            "terminal_id": "T001-001-01",
            "status": "Opened",
            "staff_id": "S001",
            "staff_name": "Test Staff",
        }

        info = terminal_claims_to_terminal_info(claims)
        assert info.staff is not None
        assert info.staff.id == "S001"
        assert info.staff.name == "Test Staff"
        assert info.staff.tenant_id == "T001"

    def test_roundtrip(self):
        """create_terminal_token → verify → terminal_claims_to_terminal_info produces equivalent data."""
        original = _make_terminal_info(
            status="Opened",
            business_date="20260324",
            open_counter=3,
            business_counter=7,
            staff_id="S002",
            staff_name="Roundtrip Staff",
        )
        token = create_terminal_token(original)
        claims = verify_terminal_token(token)
        restored = terminal_claims_to_terminal_info(claims)

        assert restored.tenant_id == original.tenant_id
        assert restored.store_code == original.store_code
        assert restored.terminal_no == original.terminal_no
        assert restored.terminal_id == original.terminal_id
        assert restored.status == original.status
        assert restored.business_date == original.business_date
        assert restored.open_counter == original.open_counter
        assert restored.business_counter == original.business_counter
        assert restored.staff.id == original.staff.id
        assert restored.staff.name == original.staff.name


class TestTerminalBinding:
    """A terminal JWT may act only on the terminal it was issued to."""

    @pytest.mark.asyncio
    async def test_own_terminal_is_allowed(self):
        token = create_terminal_token(_make_terminal_info())
        tenant_id = await get_tenant_id_with_security("T001-001-01", None, token)
        assert tenant_id == "T001"

    @pytest.mark.asyncio
    async def test_other_terminal_is_forbidden(self):
        token = create_terminal_token(_make_terminal_info())
        with pytest.raises(HTTPException) as exc:
            await get_tenant_id_with_security("T001-001-02", None, token)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_other_terminal_by_query_is_forbidden(self):
        token = create_terminal_token(_make_terminal_info())
        with pytest.raises(HTTPException) as exc:
            await get_tenant_id_with_security_by_query("T001-001-02", None, token)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_no_target_terminal_is_allowed(self):
        token = create_terminal_token(_make_terminal_info())
        tenant_id = await get_tenant_id_with_security_by_query_optional(None, None, token)
        assert tenant_id == "T001"

    @pytest.mark.asyncio
    async def test_token_without_terminal_claim_is_forbidden(self):
        # verify_terminal_token does not require the claim; a token without it
        # must not skip the comparison.
        token = jwt.encode(
            {"token_type": "terminal", "tenant_id": "T001"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            await get_tenant_id_with_security("T001-001-01", None, token)
        assert exc.value.status_code == 403

    def test_binding_without_target_passes(self):
        verify_terminal_binding({"terminal_id": "T001-001-01"}, None)


def _path_binding_app() -> FastAPI:
    app = FastAPI()

    @app.get("/tenants/{tenant_id}/stores/{store_code}/journals")
    async def store_read(tenant_id: str = Depends(get_tenant_id_with_security_by_query_optional)):
        return {"tenant_id": tenant_id}

    @app.get("/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports")
    async def terminal_read(tenant_id: str = Depends(get_tenant_id_with_security_by_query_optional)):
        return {"tenant_id": tenant_id}

    @app.post("/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/transactions")
    async def terminal_write(tenant_id: str = Depends(get_tenant_id_with_security_by_query_optional)):
        return {"tenant_id": tenant_id}

    return app


async def _call(method: str, path: str, token: str) -> int:
    transport = ASGITransport(app=_path_binding_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.request(method, path, headers={"Authorization": f"Bearer {token}"})
    return resp.status_code


class TestPathBinding:
    """A terminal credential reads only its own store and writes only as its own terminal."""

    @pytest.mark.asyncio
    async def test_own_store_is_allowed(self):
        token = create_terminal_token(_make_terminal_info())
        assert await _call("GET", "/tenants/T001/stores/001/journals", token) == 200

    @pytest.mark.asyncio
    async def test_other_store_is_forbidden(self):
        token = create_terminal_token(_make_terminal_info())
        assert await _call("GET", "/tenants/T001/stores/002/journals", token) == 403

    @pytest.mark.asyncio
    async def test_other_terminal_of_own_store_may_be_read(self):
        # A register may ask for another register's report in its own store.
        token = create_terminal_token(_make_terminal_info())
        assert await _call("GET", "/tenants/T001/stores/001/terminals/2/reports", token) == 200

    @pytest.mark.asyncio
    async def test_write_as_own_terminal_is_allowed(self):
        token = create_terminal_token(_make_terminal_info())
        assert await _call("POST", "/tenants/T001/stores/001/terminals/1/transactions", token) == 200

    @pytest.mark.asyncio
    async def test_write_as_other_terminal_is_forbidden(self):
        token = create_terminal_token(_make_terminal_info())
        assert await _call("POST", "/tenants/T001/stores/001/terminals/2/transactions", token) == 403

    @pytest.mark.asyncio
    async def test_write_into_other_store_is_forbidden(self):
        token = create_terminal_token(_make_terminal_info())
        assert await _call("POST", "/tenants/T001/stores/002/terminals/1/transactions", token) == 403

    @pytest.mark.asyncio
    async def test_token_without_store_claim_is_forbidden(self):
        token = jwt.encode(
            {"token_type": "terminal", "tenant_id": "T001", "terminal_id": "T001-001-01", "terminal_no": 1},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        assert await _call("GET", "/tenants/T001/stores/001/journals", token) == 403

    @pytest.mark.asyncio
    async def test_user_jwt_is_not_bound(self):
        token = jwt.encode(
            {"sub": "admin", "tenant_id": "T001"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        assert await _call("POST", "/tenants/T001/stores/002/terminals/9/transactions", token) == 200

    def test_without_request_nothing_is_bound(self):
        verify_path_binding(None, None, None, None, "terminal_jwt")

    def test_terminal_no_is_compared_as_a_number(self):
        verify_path_binding("001", 1, {"store_code": "001", "terminal_no": "01"}, "POST", "api_key")

    def test_missing_terminal_no_is_forbidden_on_write(self):
        with pytest.raises(HTTPException) as exc:
            verify_path_binding("001", None, {"store_code": "001", "terminal_no": "1"}, "POST", "api_key")
        assert exc.value.status_code == 403

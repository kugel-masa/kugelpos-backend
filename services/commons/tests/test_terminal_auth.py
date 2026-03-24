"""
Unit tests for terminal JWT token generation and verification.
"""
import pytest
from datetime import timedelta
from jose import jwt

from kugel_common.config.settings import settings
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.utils.terminal_auth import create_terminal_token
from kugel_common.security import verify_terminal_token, terminal_claims_to_terminal_info


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

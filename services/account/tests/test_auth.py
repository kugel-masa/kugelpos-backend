# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from jose import jwt

from app.dependencies.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    authenticate_user,
    authenticate_superuser,
    get_current_user,
    generate_tenant_id,
    SECRET_KEY,
    ALGORITHM,
)
from app.api.v1.schemas import UserAccountInDB


def make_user(
    username="testuser",
    tenant_id="T001",
    is_active=True,
    is_superuser=False,
    password="password123",
):
    hashed = get_password_hash(password)
    return UserAccountInDB(
        username=username,
        password=password,
        hashed_password=hashed,
        tenant_id=tenant_id,
        is_active=is_active,
        is_superuser=is_superuser,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# verify_password / get_password_hash
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_verify_correct_password(self):
        hashed = get_password_hash("secret")
        assert verify_password("secret", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("secret")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_not_plain_text(self):
        hashed = get_password_hash("secret")
        assert hashed != "secret"

    def test_same_password_produces_different_hashes(self):
        # bcrypt salts each hash differently
        h1 = get_password_hash("secret")
        h2 = get_password_hash("secret")
        assert h1 != h2

    def test_verify_empty_password(self):
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------

class TestCreateAccessToken:
    def test_token_contains_payload(self):
        data = {"sub": "user1", "tenant_id": "T001"}
        token = create_access_token(data)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user1"
        assert payload["tenant_id"] == "T001"

    def test_token_has_expiry(self):
        data = {"sub": "user1"}
        token = create_access_token(data)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_custom_expires_delta(self):
        data = {"sub": "user1"}
        delta = timedelta(minutes=5)
        before = datetime.now(timezone.utc)
        token = create_access_token(data, expires_delta=delta)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > before
        assert exp <= before + delta + timedelta(seconds=5)

    def test_default_expiry_applied_when_no_delta(self):
        data = {"sub": "user1"}
        before = datetime.now(timezone.utc)
        token = create_access_token(data)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        # Should expire more than 1 minute from now (uses ACCESS_TOKEN_EXPIRE_MINUTES)
        assert exp > before + timedelta(minutes=1)


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------

class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_success(self):
        user = make_user(username="alice", password="pass123")
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "username": "alice",
            "password": "pass123",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": True,
            "is_superuser": False,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_user("alice", "pass123", "T001")
        assert result is not False
        assert result.username == "alice"

    @pytest.mark.asyncio
    async def test_user_not_found_returns_false(self):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_user("ghost", "pass", "T001")
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_password_returns_false(self):
        user = make_user(username="alice", password="correct")
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "username": "alice",
            "password": "correct",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": True,
            "is_superuser": False,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_user("alice", "wrong", "T001")
        assert result is False

    @pytest.mark.asyncio
    async def test_inactive_user_returns_false(self):
        user = make_user(username="alice", password="pass", is_active=False)
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "username": "alice",
            "password": "pass",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": False,
            "is_superuser": False,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_user("alice", "pass", "T001")
        assert result is False


# ---------------------------------------------------------------------------
# authenticate_superuser
# ---------------------------------------------------------------------------

class TestAuthenticateSuperuser:
    @pytest.mark.asyncio
    async def test_superuser_success(self):
        user = make_user(username="admin", is_superuser=True, is_active=True)
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "username": "admin",
            "password": "pass",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": True,
            "is_superuser": True,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_superuser("admin", "T001")
        assert result is not False
        assert result.is_superuser is True

    @pytest.mark.asyncio
    async def test_non_superuser_returns_false(self):
        user = make_user(username="alice", is_superuser=False)
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "username": "alice",
            "password": "pass",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": True,
            "is_superuser": False,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_superuser("alice", "T001")
        assert result is False

    @pytest.mark.asyncio
    async def test_inactive_superuser_returns_false(self):
        user = make_user(username="admin", is_superuser=True, is_active=False)
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {
            "username": "admin",
            "password": "pass",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": False,
            "is_superuser": True,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await authenticate_superuser("admin", "T001")
        assert result is False


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def _make_token(self, username="alice", tenant_id="T001", is_superuser=False):
        data = {"sub": username, "tenant_id": tenant_id, "is_superuser": is_superuser}
        return create_access_token(data)

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        user = make_user(username="alice")
        user_dict = {
            "username": "alice",
            "password": "pass",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": True,
            "is_superuser": False,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = user_dict
        token = self._make_token()
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await get_current_user(token)
        assert result.username == "alice"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user("invalid.token.here")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_missing_sub_raises_401(self):
        # Token with no "sub" field
        data = {"tenant_id": "T001"}
        token = create_access_token(data)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_missing_tenant_id_raises_401(self):
        # Token with no "tenant_id" field
        data = {"sub": "alice"}
        token = create_access_token(data)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_in_db_raises_401(self):
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None
        token = self._make_token()
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(token)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_is_superuser_preserved_from_token(self):
        user = make_user(username="admin", is_superuser=False)
        user_dict = {
            "username": "admin",
            "password": "pass",
            "hashed_password": user.hashed_password,
            "tenant_id": "T001",
            "is_active": True,
            "is_superuser": False,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = user_dict
        # Token claims is_superuser=True (elevated at token creation time)
        token = self._make_token(username="admin", is_superuser=True)
        with patch("app.dependencies.auth.get_user_collection", return_value=mock_collection):
            result = await get_current_user(token)
        assert result.is_superuser is True


# ---------------------------------------------------------------------------
# generate_tenant_id
# ---------------------------------------------------------------------------

class TestGenerateTenantId:
    @pytest.mark.asyncio
    async def test_generates_unique_id_when_db_not_exists(self):
        mock_client = AsyncMock()
        mock_client.list_database_names.return_value = []
        with patch("app.dependencies.auth.db_helper") as mock_db:
            mock_db.get_client_async = AsyncMock(return_value=mock_client)
            result = await generate_tenant_id()
        # Format: one uppercase letter + 4 digits
        assert len(result) == 5
        assert result[0].isupper()
        assert result[1:].isdigit()

    @pytest.mark.asyncio
    async def test_retries_when_db_already_exists(self):
        """First generated ID conflicts, second is accepted."""
        mock_client = AsyncMock()
        # We'll control the side effect via the list_database_names responses
        # The test patches generate_tenant_id internals via db_helper
        call_count = 0

        async def fake_list_db_names():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return a list that includes every possible name to force retry once
                # We patch more surgically below instead
                return ["db_account_A1234"]
            return []

        mock_client.list_database_names.side_effect = fake_list_db_names

        with patch("app.dependencies.auth.db_helper") as mock_db:
            mock_db.get_client_async = AsyncMock(return_value=mock_client)
            with patch("app.dependencies.auth.settings") as mock_settings:
                mock_settings.DB_NAME_PREFIX = "db_account"
                # Force the first random id to be A1234, second call will use a different random
                with patch("app.dependencies.auth.random.choice", side_effect=["A", "B"]):
                    with patch("app.dependencies.auth.random.randint", side_effect=[1234, 5678]):
                        result = await generate_tenant_id()
        assert result == "B5678"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_uses_preferred_tenant_id_when_provided(self):
        mock_client = AsyncMock()
        mock_client.list_database_names.return_value = []
        user = MagicMock()
        user.tenant_id = "T999"
        with patch("app.dependencies.auth.db_helper") as mock_db:
            mock_db.get_client_async = AsyncMock(return_value=mock_client)
            with patch("app.dependencies.auth.settings") as mock_settings:
                mock_settings.DB_NAME_PREFIX = "db_account"
                result = await generate_tenant_id(user)
        assert result == "T999"

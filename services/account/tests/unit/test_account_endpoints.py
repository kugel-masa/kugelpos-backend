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
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.v1.account import router
from app.api.v1.schemas import UserAccountInDB
from app.dependencies.auth import get_password_hash, create_access_token

# POST /accounts/register requires the tenant provisioning key (issue #138)
PROVISIONING_HEADERS = {
    "X-Provisioning-Key": os.environ.get(
        "TENANT_PROVISIONING_KEY", "dev-tenant-provisioning-key-for-development-only"
    )
}


def make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/accounts")
    return app


def make_user_dict(
    username="alice",
    tenant_id="T001",
    is_active=True,
    is_superuser=False,
    password="pass123",
):
    return {
        "username": username,
        "password": "pass123",
        "hashed_password": get_password_hash(password),
        "tenant_id": tenant_id,
        "is_active": is_active,
        "is_superuser": is_superuser,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": None,
        "last_login": None,
    }


# ---------------------------------------------------------------------------
# login_for_access_token  POST /api/v1/accounts/token
# ---------------------------------------------------------------------------

class TestLoginForAccessToken:
    @pytest.mark.asyncio
    async def test_login_success_returns_token(self):
        user_dict = make_user_dict()
        user = UserAccountInDB(**user_dict)
        app = make_app()

        with patch("app.api.v1.account.authenticate_user", return_value=user), \
             patch("app.api.v1.account.get_user_collection") as mock_col:
            mock_collection = AsyncMock()
            mock_collection.update_one.return_value = MagicMock(modified_count=1)
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/token",
                    data={"username": "alice", "password": "pass123", "client_id": "T001"},
                )

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_credentials_returns_401(self):
        app = make_app()

        with patch("app.api.v1.account.authenticate_user", return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/token",
                    data={"username": "alice", "password": "wrong", "client_id": "T001"},
                )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_last_login_update_failure_still_returns_token(self):
        """last_login 更新に失敗してもログインは成功する。"""
        user_dict = make_user_dict()
        user = UserAccountInDB(**user_dict)
        app = make_app()

        with patch("app.api.v1.account.authenticate_user", return_value=user), \
             patch("app.api.v1.account.get_user_collection") as mock_col:
            mock_collection = AsyncMock()
            mock_collection.update_one.side_effect = Exception("DB error")
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/token",
                    data={"username": "alice", "password": "pass123", "client_id": "T001"},
                )

        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_login_last_login_not_modified_still_returns_token(self):
        """update_one が 0 件更新でも例外が内部で処理されトークンを返す。"""
        user_dict = make_user_dict()
        user = UserAccountInDB(**user_dict)
        app = make_app()

        with patch("app.api.v1.account.authenticate_user", return_value=user), \
             patch("app.api.v1.account.get_user_collection") as mock_col:
            mock_collection = AsyncMock()
            mock_collection.update_one.return_value = MagicMock(modified_count=0)
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/token",
                    data={"username": "alice", "password": "pass123", "client_id": "T001"},
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_logger_records_login_succeeded(self):
        """Successful login must be audited (security event)."""
        user_dict = make_user_dict()
        user = UserAccountInDB(**user_dict)
        app = make_app()

        with patch("app.api.v1.account.authenticate_user", return_value=user), \
             patch("app.api.v1.account.get_user_collection") as mock_col, \
             patch("app.api.v1.account.audit_logger") as mock_audit:
            mock_collection = AsyncMock()
            mock_collection.update_one.return_value = MagicMock(modified_count=1)
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/token",
                    data={"username": "alice", "password": "pass123", "client_id": "T001"},
                )

        assert response.status_code == 200
        info_calls = [c for c in mock_audit.info.call_args_list if "Login succeeded" in c.args[0]]
        assert len(info_calls) == 1, mock_audit.info.call_args_list

    @pytest.mark.asyncio
    async def test_audit_logger_records_login_failed(self):
        """Failed login must be audited as WARNING (brute-force signal)."""
        app = make_app()

        with patch("app.api.v1.account.authenticate_user", return_value=False), \
             patch("app.api.v1.account.audit_logger") as mock_audit:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/token",
                    data={"username": "alice", "password": "wrong", "client_id": "T001"},
                )

        assert response.status_code == 401
        warn_calls = [c for c in mock_audit.warning.call_args_list if "Login failed" in c.args[0]]
        assert len(warn_calls) == 1, mock_audit.warning.call_args_list


# ---------------------------------------------------------------------------
# register_super_user  POST /api/v1/accounts/register
# ---------------------------------------------------------------------------

class TestRegisterSuperUser:
    @pytest.mark.asyncio
    async def test_register_superuser_success(self):
        from app.dependencies.auth import generate_tenant_id as real_generate_tenant_id

        async def mock_generate_tenant_id():
            return "T999"

        app = make_app()
        app.dependency_overrides[real_generate_tenant_id] = mock_generate_tenant_id

        with patch("app.api.v1.account.database_setup") as mock_setup, \
             patch("app.api.v1.account.get_user_collection") as mock_col, \
             patch("app.api.v1.account.send_info_notification", new_callable=AsyncMock):
            mock_setup.execute = AsyncMock()
            mock_collection = AsyncMock()
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/register",
                    headers=PROVISIONING_HEADERS,
                    json={"username": "admin", "password": "adminpass"},
                )

        assert response.status_code == 201
        body = response.json()
        assert body["data"]["username"] == "admin"
        assert body["data"]["isActive"] is True
        assert body["data"]["isSuperuser"] is True
        # password is masked
        assert body["data"]["password"] == "*****"

    @pytest.mark.asyncio
    async def test_register_superuser_hashes_password(self):
        """DB に保存されるパスワードがハッシュ化されていること。"""
        from app.dependencies.auth import generate_tenant_id as real_generate_tenant_id

        async def mock_generate_tenant_id():
            return "T999"

        inserted = {}
        app = make_app()
        app.dependency_overrides[real_generate_tenant_id] = mock_generate_tenant_id

        async def fake_insert(doc):
            inserted.update(doc)

        with patch("app.api.v1.account.database_setup") as mock_setup, \
             patch("app.api.v1.account.get_user_collection") as mock_col, \
             patch("app.api.v1.account.send_info_notification", new_callable=AsyncMock):
            mock_setup.execute = AsyncMock()
            mock_collection = AsyncMock()
            mock_collection.insert_one.side_effect = fake_insert
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.post(
                    "/api/v1/accounts/register",
                    headers=PROVISIONING_HEADERS,
                    json={"username": "admin", "password": "plainpass"},
                )

        assert inserted.get("hashed_password") != "plainpass"
        assert inserted.get("hashed_password", "").startswith("$2")  # bcrypt prefix


class TestRegisterRequiresProvisioningKey:
    """Registration takes no user token, and was open to anyone (issue #138)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "headers, reason",
        [({}, "missing"), ({"X-Provisioning-Key": "not-the-key"}, "wrong")],
    )
    async def test_refused_without_the_key(self, headers, reason):
        from app.dependencies.auth import generate_tenant_id as real_generate_tenant_id

        generate = AsyncMock(return_value="T999")
        app = make_app()
        app.dependency_overrides[real_generate_tenant_id] = generate

        with patch("app.api.v1.account.database_setup") as mock_setup, \
             patch("app.api.v1.account.get_user_collection") as mock_col, \
             patch("app.dependencies.auth.audit_logger") as mock_audit:
            mock_setup.execute = AsyncMock()
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/register",
                    headers=headers,
                    json={"username": "admin", "password": "adminpass"},
                )

        assert response.status_code == 401
        # Refused before a tenant ID is looked for or anything is created
        generate.assert_not_awaited()
        mock_setup.execute.assert_not_awaited()
        mock_col.assert_not_called()
        warn = [c for c in mock_audit.warning.call_args_list if "refused" in c.args[0]]
        assert len(warn) == 1
        assert reason in warn[0].args[1]

    @pytest.mark.asyncio
    async def test_an_unset_key_refuses_everything(self, monkeypatch):
        """The settings refuse to start without a key; if they are bypassed,
        an empty key must not match an empty header."""
        from app.config.settings import settings

        monkeypatch.setattr(settings, "TENANT_PROVISIONING_KEY", "")
        app = make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/accounts/register",
                headers={"X-Provisioning-Key": ""},
                json={"username": "admin", "password": "adminpass"},
            )
        assert response.status_code == 401


class TestProvisioningKeySettings:
    def _settings(self, **env):
        from app.config.settings_provisioning import TenantProvisioningSettings

        return TenantProvisioningSettings(**env)

    def test_a_key_of_ones_own_is_accepted(self):
        key = "k" * 32
        assert self._settings(TENANT_PROVISIONING_KEY=key).TENANT_PROVISIONING_KEY == key

    @pytest.mark.parametrize(
        "key, message",
        [
            (" " + "k" * 32, "printable ASCII"),
            ("k" * 32 + "\n", "printable ASCII"),
            ("k" * 31 + " k", "printable ASCII"),
            ("k" * 31 + "\u00fc", "printable ASCII"),
            ("k" * 31, "shorter than 32"),
        ],
        ids=["leading-space", "trailing-newline", "inner-space", "non-ascii", "short"],
    )
    def test_a_key_a_header_cannot_carry_refuses_to_start(self, key, message):
        """A header loses surrounding whitespace and is not reliably decoded
        beyond ASCII, so such a key would refuse every call; and nothing rate
        limits registration, so the key has to be long."""
        with pytest.raises(ValueError, match=message):
            self._settings(TENANT_PROVISIONING_KEY=key, ALLOW_INSECURE_DEV_SECRETS=True)

    def test_the_service_settings_read_the_key_from_the_environment(self, monkeypatch):
        """The check runs on the account service's own Settings, composed from
        several classes, and reads the environment as deployed."""
        from app.config.settings import Settings

        monkeypatch.setenv("TENANT_PROVISIONING_KEY", "e" * 40)
        assert Settings().TENANT_PROVISIONING_KEY == "e" * 40

        # The other secrets of one's own, so that only the provisioning key is refused
        monkeypatch.setenv("SECRET_KEY", "s" * 48)
        monkeypatch.setenv("PUBSUB_NOTIFY_API_KEY", "p" * 48)
        monkeypatch.setenv("ALLOW_INSECURE_DEV_SECRETS", "false")
        assert Settings().TENANT_PROVISIONING_KEY == "e" * 40

        monkeypatch.setenv("TENANT_PROVISIONING_KEY", "dev-tenant-provisioning-key-for-development-only")
        with pytest.raises(ValueError, match="TENANT_PROVISIONING_KEY is a value published"):
            Settings()

        monkeypatch.setenv("TENANT_PROVISIONING_KEY", "   ")
        with pytest.raises(ValueError, match="TENANT_PROVISIONING_KEY is not set"):
            Settings()

    @pytest.mark.parametrize("key", ["", "   "])
    def test_an_empty_key_refuses_to_start_even_in_development(self, key):
        with pytest.raises(ValueError, match="TENANT_PROVISIONING_KEY is not set"):
            self._settings(TENANT_PROVISIONING_KEY=key, ALLOW_INSECURE_DEV_SECRETS=True)

    def test_the_published_key_refuses_to_start(self):
        with pytest.raises(ValueError, match="published"):
            self._settings(
                TENANT_PROVISIONING_KEY="dev-tenant-provisioning-key-for-development-only",
                ALLOW_INSECURE_DEV_SECRETS=False,
            )

    def test_the_published_key_is_allowed_for_development(self):
        assert self._settings(
            TENANT_PROVISIONING_KEY="dev-tenant-provisioning-key-for-development-only",
            ALLOW_INSECURE_DEV_SECRETS=True,
        )


# ---------------------------------------------------------------------------
# register_user_by_superuser  POST /api/v1/accounts/register/user
# ---------------------------------------------------------------------------

class TestRegisterUserBySuperuser:
    def _make_token(self, username="admin", tenant_id="T001", is_superuser=True):
        return create_access_token({"sub": username, "tenant_id": tenant_id, "is_superuser": is_superuser})

    @pytest.mark.asyncio
    async def test_register_user_by_superuser_success(self):
        from app.dependencies.auth import get_current_user as real_get_current_user

        superuser_dict = make_user_dict(username="admin", is_superuser=True)
        superuser = UserAccountInDB(**superuser_dict)
        app = make_app()
        app.dependency_overrides[real_get_current_user] = lambda: superuser
        token = self._make_token()

        with patch("app.api.v1.account.authenticate_superuser", return_value=superuser), \
             patch("app.api.v1.account.get_user_collection") as mock_col:
            mock_collection = AsyncMock()
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/register/user",
                    json={"username": "newuser", "password": "newpass"},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 201
        body = response.json()
        assert body["data"]["username"] == "newuser"
        assert body["data"]["isSuperuser"] is False
        assert body["data"]["password"] == "*****"

    @pytest.mark.asyncio
    async def test_register_user_by_non_superuser_returns_401(self):
        """Non-superuser calling this endpoint returns 401."""
        from app.dependencies.auth import get_current_user as real_get_current_user

        regular_user_dict = make_user_dict(username="alice", is_superuser=False)
        regular_user = UserAccountInDB(**regular_user_dict)
        app = make_app()
        app.dependency_overrides[real_get_current_user] = lambda: regular_user
        token = self._make_token(username="alice", is_superuser=False)

        with patch("app.api.v1.account.authenticate_superuser", return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounts/register/user",
                    json={"username": "newuser", "password": "newpass"},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_register_user_hashes_password(self):
        """Registered user's password is hashed before storage."""
        from app.dependencies.auth import get_current_user as real_get_current_user

        superuser_dict = make_user_dict(username="admin", is_superuser=True)
        superuser = UserAccountInDB(**superuser_dict)
        inserted = {}
        app = make_app()
        app.dependency_overrides[real_get_current_user] = lambda: superuser
        token = self._make_token()

        async def fake_insert(doc):
            inserted.update(doc)

        with patch("app.api.v1.account.authenticate_superuser", return_value=superuser), \
             patch("app.api.v1.account.get_user_collection") as mock_col:
            mock_collection = AsyncMock()
            mock_collection.insert_one.side_effect = fake_insert
            mock_col.return_value = mock_collection

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.post(
                    "/api/v1/accounts/register/user",
                    json={"username": "newuser", "password": "plainpass"},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert inserted.get("hashed_password") != "plainpass"
        assert inserted.get("hashed_password", "").startswith("$2")

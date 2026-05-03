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
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.v1.account import router
from app.api.v1.schemas import UserAccountInDB
from app.dependencies.auth import get_password_hash, create_access_token


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
                    json={"username": "admin", "password": "plainpass"},
                )

        assert inserted.get("hashed_password") != "plainpass"
        assert inserted.get("hashed_password", "").startswith("$2")  # bcrypt prefix


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

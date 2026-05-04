# Copyright 2026 masa@kugel
"""Authentication / authorisation boundary e2e tests.

Verifies the security perimeter holds against:
  * cross-tenant access (admin of tenant A can't read tenant B data)
  * expired JWT tokens (rejected with 401)
  * malformed / missing / wrong-signature tokens (rejected with 401)

Pulls a real admin JWT from the live account service for the positive
controls, and forges JWTs with the project's test SECRET_KEY for the
expired / wrong-signature negatives.
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest


# Match commons.config.settings_auth.SECRET_KEY default (development).
DEV_SECRET_KEY = "test-secret-key-for-development-only"
ALG = "HS256"


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


def _new_tenant_id() -> str:
    return "AUTH" + uuid.uuid4().hex[:8].upper()


def _live_admin_token(tenant_id: str) -> str:
    """Register + login admin against the running account service."""
    with _client("URL_ACCOUNT") as c:
        c.post("/api/v1/accounts/register", json={
            "username": "admin", "password": "admin", "tenant_id": tenant_id,
        })
        resp = c.post("/api/v1/accounts/token", data={
            "username": "admin", "password": "admin", "client_id": tenant_id,
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


def _forge_jwt(*, tenant_id: str, expired: bool = False, secret: str = DEV_SECRET_KEY) -> str:
    """Build a JWT with chosen exp / signing key.

    expired=True puts exp 1 day in the past so any sane validation rejects.
    Pass an alternate `secret` to test signature mismatch.
    """
    if expired:
        exp = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        exp = datetime.now(timezone.utc) + timedelta(hours=1)

    payload = {
        "sub": "admin",
        "tenant_id": tenant_id,
        "is_superuser": True,
        "exp": exp,
    }
    return jwt.encode(payload, secret, algorithm=ALG)


def _setup_tenant(tenant_id: str, token: str):
    """POST /tenants on terminal so per-tenant DBs exist (fan-out)."""
    h = {"Authorization": f"Bearer {token}"}
    with _client("URL_TERMINAL") as c:
        c.post("/api/v1/tenants", json={
            "tenant_id": tenant_id, "tenant_name": "Auth Test",
            "stores": [], "tags": ["auth-boundary"],
        }, headers=h)


# ---------------------------------------------------------------------------
# Cross-tenant denial
# ---------------------------------------------------------------------------


def test_cross_tenant_admin_cannot_read_other_tenant():
    """Admin JWT for tenant A used against tenant B's resource → 4xx."""
    tenant_a = _new_tenant_id()
    tenant_b = _new_tenant_id()
    token_a = _live_admin_token(tenant_a)
    _setup_tenant(tenant_a, token_a)

    # Tenant B exists too (fresh) so the URL itself is valid.
    token_b = _live_admin_token(tenant_b)
    _setup_tenant(tenant_b, token_b)

    with _client("URL_TERMINAL") as c:
        # admin-A tries to GET admin-B's tenant info.
        resp = c.get(
            f"/api/v1/tenants/{tenant_b}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
    # Cross-tenant read must be rejected. Acceptable shapes:
    #   * 401 / 403 — explicit auth/authz rejection
    #   * 404 — record hidden
    #   * 400 with "does not match" / "tenant_id" — current behaviour
    #     in kugel_common.security.verify_tenant_id which raises
    #     HTTPException(400) for tenant mismatch
    # A 200 with the OTHER tenant's data would be the security bug.
    body = resp.text.lower()
    is_denied = (
        resp.status_code in (401, 403, 404)
        or (resp.status_code == 400 and ("does not match" in body or "tenant_id" in body))
    )
    assert is_denied, (
        f"Cross-tenant access should be denied; got {resp.status_code}: {resp.text}"
    )
    # Defence-in-depth: if 200, ensure body doesn't contain tenant B's id
    if resp.status_code == 200:
        assert tenant_b not in resp.text, "200 leaked tenant_b data!"


# ---------------------------------------------------------------------------
# Expired token
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url_env, path",
    [
        ("URL_TERMINAL", "/api/v1/terminals"),
        ("URL_MASTER_DATA", "/api/v1/tenants/T6216/staff"),
        ("URL_JOURNAL", "/api/v1/tenants/T6216/stores/5678/journals"),
    ],
)
def test_expired_jwt_rejected(url_env, path):
    """A JWT with exp in the past is rejected with HTTP 401."""
    expired = _forge_jwt(tenant_id="T6216", expired=True)
    with _client(url_env) as c:
        resp = c.get(path, headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401, (
        f"Expired JWT should yield 401; got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Wrong-signature / malformed token
# ---------------------------------------------------------------------------


def test_wrong_signature_jwt_rejected():
    """A JWT signed with a DIFFERENT secret is rejected with 401."""
    bad = _forge_jwt(tenant_id="T6216", secret="not-the-real-secret")
    with _client("URL_TERMINAL") as c:
        resp = c.get("/api/v1/terminals", headers={"Authorization": f"Bearer {bad}"})
    assert resp.status_code == 401, resp.text


def test_malformed_token_rejected():
    """Garbage-shaped Authorization header → 401."""
    with _client("URL_TERMINAL") as c:
        resp = c.get(
            "/api/v1/terminals",
            headers={"Authorization": "Bearer this.is.not.a.jwt"},
        )
    assert resp.status_code == 401, resp.text


def test_missing_authorization_rejected():
    """No Authorization header → 401."""
    with _client("URL_TERMINAL") as c:
        resp = c.get("/api/v1/terminals")
    assert resp.status_code == 401, resp.text

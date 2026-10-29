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

from .test_concurrency import _bootstrap


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
# Cross-terminal denial
# ---------------------------------------------------------------------------


def _terminal_jwts(tenant_id: str, admin_token: str, store_code: str) -> tuple[str, str, str, str]:
    """Create two terminals in one store; return (terminal A, terminal B, JWT of A, API key of A)."""
    h = {"Authorization": f"Bearer {admin_token}"}
    with _client("URL_TERMINAL") as c:
        c.post(f"/api/v1/tenants/{tenant_id}/stores", json={
            "store_code": store_code, "store_name": "Auth Test Store",
        }, headers=h).raise_for_status()
        created = []
        for terminal_no in (1, 2):
            resp = c.post("/api/v1/terminals", json={
                "store_code": store_code, "terminal_no": terminal_no,
                "description": "auth-boundary",
            }, headers=h)
            resp.raise_for_status()
            created.append(resp.json()["data"])
        resp = c.post("/api/v1/auth/token", headers={"X-API-KEY": created[0]["apiKey"]})
        resp.raise_for_status()
    return (
        created[0]["terminalId"],
        created[1]["terminalId"],
        resp.json()["data"]["access_token"],
        created[0]["apiKey"],
    )


def test_terminal_jwt_cannot_act_on_another_terminal():
    """Terminal A's JWT on terminal B → 403, on both auth paths (#251).

    terminal reads the target from the URL path; journal (and every other
    service through kugel_common) reads it from the terminal_id query.
    """
    tenant_id = _new_tenant_id()
    admin_token = _live_admin_token(tenant_id)
    _setup_tenant(tenant_id, admin_token)
    store_code = "5678"
    terminal_a, terminal_b, jwt_a, _ = _terminal_jwts(tenant_id, admin_token, store_code)
    h = {"Authorization": f"Bearer {jwt_a}"}

    with _client("URL_TERMINAL") as c:
        assert c.get(f"/api/v1/terminals/{terminal_a}", headers=h).status_code == 200
        resp = c.get(f"/api/v1/terminals/{terminal_b}", headers=h)
        assert resp.status_code == 403, resp.text
        resp = c.post(f"/api/v1/terminals/{terminal_b}/open", json={"initial_amount": 0}, headers=h)
        assert resp.status_code == 403, resp.text

    journals = f"/api/v1/tenants/{tenant_id}/stores/{store_code}/journals"
    with _client("URL_JOURNAL") as c:
        assert c.get(journals, params={"terminal_id": terminal_a}, headers=h).status_code == 200
        resp = c.get(journals, params={"terminal_id": terminal_b}, headers=h)
        assert resp.status_code == 403, resp.text


def test_terminal_credential_is_bound_to_its_store():
    """A terminal reads only its own store and writes only as itself (C10).

    The store_code / terminal_no in the URL are compared with the credential,
    on both the terminal JWT and the API-key paths.
    """
    tenant_id = _new_tenant_id()
    admin_token = _live_admin_token(tenant_id)
    _setup_tenant(tenant_id, admin_token)
    store_code, other_store = "5678", "5679"
    terminal_a, _, jwt_a, api_key_a = _terminal_jwts(tenant_id, admin_token, store_code)
    h = {"Authorization": f"Bearer {jwt_a}"}
    stores = f"/api/v1/tenants/{tenant_id}/stores"

    with _client("URL_JOURNAL") as c:
        assert c.get(f"{stores}/{store_code}/journals", headers=h).status_code == 200
        resp = c.get(f"{stores}/{other_store}/journals", headers=h)
        assert resp.status_code == 403, resp.text
        # A write is bound to the terminal too; the binding is checked before the body.
        resp = c.post(f"{stores}/{store_code}/terminals/2/transactions", json={}, headers=h)
        assert resp.status_code == 403, resp.text

    with _client("URL_STOCK") as c:
        assert c.get(f"{stores}/{store_code}/stock", headers=h).status_code == 200
        resp = c.get(f"{stores}/{other_store}/stock", headers=h)
        assert resp.status_code == 403, resp.text
        # API key of terminal A, naming A in the query, but another store in the path.
        resp = c.get(
            f"{stores}/{other_store}/stock",
            params={"terminal_id": terminal_a},
            headers={"X-API-KEY": api_key_a},
        )
        assert resp.status_code == 403, resp.text

    with _client("URL_CART") as c:
        # Another register of the same store may be listed; another store may not.
        resp = c.get(f"{stores}/{store_code}/terminals/2/transactions", headers=h)
        assert resp.status_code == 200, resp.text
        resp = c.get(f"{stores}/{other_store}/terminals/1/transactions", headers=h)
        assert resp.status_code == 403, resp.text


def test_terminal_credential_cannot_write_masters():
    """A register's credential cannot change tenant masters; the back office can."""
    tenant_id = _new_tenant_id()
    admin_token = _live_admin_token(tenant_id)
    _setup_tenant(tenant_id, admin_token)
    terminal_a, _, jwt_a, api_key_a = _terminal_jwts(tenant_id, admin_token, "5678")
    admin = {"Authorization": f"Bearer {admin_token}"}
    staff = f"/api/v1/tenants/{tenant_id}/staff"
    body = {"name": "Staff", "pin": "1234", "roles": ["staff"]}

    with _client("URL_MASTER_DATA") as c:
        assert c.post(staff, json={"id": "S900", **body}, headers=admin).status_code == 201
        escalate = {"name": "Staff", "pin": "0000", "roles": ["manager"]}
        resp = c.put(f"{staff}/S900", json=escalate, headers={"Authorization": f"Bearer {jwt_a}"})
        assert resp.status_code == 403, resp.text
        resp = c.put(
            f"{staff}/S900", params={"terminal_id": terminal_a}, json=escalate,
            headers={"X-API-KEY": api_key_a},
        )
        assert resp.status_code == 403, resp.text
        # Reads stay open to the register.
        assert c.get(f"{staff}/S900", headers={"Authorization": f"Bearer {jwt_a}"}).status_code == 200
        assert c.put(f"{staff}/S900", json=body, headers=admin).status_code == 200


def test_cart_is_used_only_within_its_tenant_and_store():
    """The cart cache is keyed by cart_id alone; a cart_id is not a credential."""
    tenant_id, other_tenant = _new_tenant_id(), _new_tenant_id()
    owner, owner_key = _bootstrap(tenant_id, "A001", 1, "ITEM1")
    other_store, other_store_key = _bootstrap(tenant_id, "B001", 1, "ITEM1")
    stranger, stranger_key = _bootstrap(other_tenant, "X001", 1, "ITEM1")
    line = [{"itemCode": "ITEM1", "quantity": 1}]

    with _client("URL_CART") as c:
        resp = c.post("/api/v1/carts", params={"terminal_id": owner}, json={"terminal_id": owner},
                      headers={"X-API-KEY": owner_key})
        assert resp.status_code == 201, resp.text
        cart_id = resp.json()["data"]["cartId"]
        for terminal_id, api_key in ((other_store, other_store_key), (stranger, stranger_key)):
            resp = c.post(f"/api/v1/carts/{cart_id}/lineItems", params={"terminal_id": terminal_id},
                          json=line, headers={"X-API-KEY": api_key})
            assert resp.status_code == 403, resp.text
        resp = c.post(f"/api/v1/carts/{cart_id}/lineItems", params={"terminal_id": owner},
                      json=line, headers={"X-API-KEY": owner_key})
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["data"]["lineItems"]) == 1


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

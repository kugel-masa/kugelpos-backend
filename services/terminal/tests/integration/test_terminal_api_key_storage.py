# Copyright 2026 masa@kugel
"""A terminal's API key is stored as a digest, and replaced rather than shown (#136).

Against MongoDB: what POST /terminals writes, that the key still authenticates,
that POST /terminals/{id}/api-key invalidates the old key, that a record still
holding a plaintext key keeps working and is sealed, and that the service's own
outbound calls no longer carry the key it does not have.
"""
import os

import pytest
from fastapi import status

from kugel_common.utils.terminal_api_key import hash_api_key

from .test_terminal_lifecycle import _create_terminal


async def _terminal_collection():
    from kugel_common.database import database as db_helper

    from app.config.settings import settings

    tenant_id = os.environ.get("TENANT_ID")
    db = await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}")
    return db[settings.DB_COLLECTION_NAME_TERMINAL_INFO]


async def _token_status(http_client, api_key, terminal_id=None):
    url = "/api/v1/auth/token" + (f"?terminal_id={terminal_id}" if terminal_id else "")
    response = await http_client.post(url, headers={"X-API-KEY": api_key})
    return response.status_code


async def _plant_legacy_terminal(terminal_id: str, api_key: str):
    """Rewrite a terminal as a record from before #136: plaintext, no digest."""
    collection = await _terminal_collection()
    await collection.update_one(
        {"terminal_id": terminal_id},
        {"$set": {"api_key": api_key}, "$unset": {"api_key_hash": ""}},
    )


@pytest.mark.asyncio
async def test_create_stores_the_digest_and_returns_the_key_once(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    stored = await (await _terminal_collection()).find_one({"terminal_id": terminal_id})
    assert not stored.get("api_key")
    assert stored["api_key_hash"] == hash_api_key(api_key)

    # The key authenticates by terminal_id and by the scan
    assert await _token_status(http_client, api_key, terminal_id) == status.HTTP_200_OK
    assert await _token_status(http_client, api_key) == status.HTTP_200_OK

    # And can never be read back
    response = await http_client.get(f"/api/v1/terminals/{terminal_id}?include_api_key=true", headers=admin_header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["apiKey"] == "****"


@pytest.mark.asyncio
async def test_reissue_invalidates_the_old_key(http_client, admin_header, mock_outbound_services):
    terminal_id, old_key = await _create_terminal(http_client, admin_header)

    response = await http_client.post(f"/api/v1/terminals/{terminal_id}/api-key", headers=admin_header)
    assert response.status_code == status.HTTP_200_OK, response.text
    new_key = response.json()["data"]["apiKey"]
    assert new_key and new_key != old_key

    assert await _token_status(http_client, old_key, terminal_id) == status.HTTP_401_UNAUTHORIZED
    assert await _token_status(http_client, old_key) == status.HTTP_401_UNAUTHORIZED
    assert await _token_status(http_client, new_key, terminal_id) == status.HTTP_200_OK

    stored = await (await _terminal_collection()).find_one({"terminal_id": terminal_id})
    assert stored["api_key_hash"] == hash_api_key(new_key)
    assert not stored.get("api_key")


@pytest.mark.asyncio
async def test_a_terminal_cannot_reissue_its_own_key(http_client, admin_header, mock_outbound_services):
    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    by_key = await http_client.post(f"/api/v1/terminals/{terminal_id}/api-key", headers={"X-API-KEY": api_key})
    assert by_key.status_code == status.HTTP_403_FORBIDDEN

    token = (await http_client.post(
        f"/api/v1/auth/token?terminal_id={terminal_id}", headers={"X-API-KEY": api_key}
    )).json()["data"]["access_token"]
    by_token = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/api-key", headers={"Authorization": f"Bearer {token}"}
    )
    assert by_token.status_code == status.HTTP_403_FORBIDDEN

    # The key was not replaced
    assert await _token_status(http_client, api_key, terminal_id) == status.HTTP_200_OK


@pytest.mark.asyncio
@pytest.mark.parametrize("by_terminal_id", [True, False])
async def test_a_legacy_plaintext_key_still_works_and_is_sealed(
    http_client, admin_header, mock_outbound_services, by_terminal_id
):
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    legacy_key = f"legacy-{terminal_id}-0123456789"
    await _plant_legacy_terminal(terminal_id, legacy_key)

    lookup = terminal_id if by_terminal_id else None
    assert await _token_status(http_client, legacy_key, lookup) == status.HTTP_200_OK

    stored = await (await _terminal_collection()).find_one({"terminal_id": terminal_id})
    assert "api_key" not in stored
    assert stored["api_key_hash"] == hash_api_key(legacy_key)
    # Same key, now verified by digest
    assert await _token_status(http_client, legacy_key, lookup) == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_tenant_setup_seals_keys_that_are_never_used(http_client, admin_header, mock_outbound_services):
    from app.database import database_setup

    terminal_id, _ = await _create_terminal(http_client, admin_header)
    legacy_key = f"idle-{terminal_id}-0123456789"
    await _plant_legacy_terminal(terminal_id, legacy_key)

    await database_setup.seal_plaintext_api_keys(os.environ.get("TENANT_ID"))

    stored = await (await _terminal_collection()).find_one({"terminal_id": terminal_id})
    assert "api_key" not in stored
    assert stored["api_key_hash"] == hash_api_key(legacy_key)
    assert await _token_status(http_client, legacy_key, terminal_id) == status.HTTP_200_OK


def _assert_carries_terminal_token(calls, url_fragment: str, terminal_id: str, api_key: str):
    """The last outbound call to url_fragment carries the terminal's token and
    not its key. These calls sent the stored api_key; the service now holds only
    its digest, so it mints a short-lived terminal token for them (#136)."""
    from kugel_common.security import verify_terminal_token

    matching = [c for c in calls if url_fragment in str(c.request.url)]
    assert matching, f"no outbound call to {url_fragment}"
    headers = matching[-1].request.headers
    assert "x-api-key" not in headers
    scheme, _, token = headers["authorization"].partition(" ")
    assert scheme == "Bearer"
    assert verify_terminal_token(token)["terminal_id"] == terminal_id
    assert api_key not in token


async def _post_with_key(http_client, terminal_id, api_key, action, body):
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/{action}", json=body, headers={"X-API-KEY": api_key}
    )
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.asyncio
async def test_staff_verification_carries_a_service_token_not_the_key(http_client, admin_header, mock_outbound_services):
    """Sign-in verifies the staff member through master-data's internal
    endpoint (issue #323), which accepts a service-account token only. The
    terminal's key still never leaves the service (#136)."""
    import os

    from kugel_common.security import verify_token

    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    await _post_with_key(http_client, terminal_id, api_key, "sign-in", {"staff_id": "S001"})

    matching = [c for c in mock_outbound_services.calls if "/internal/tenants/" in str(c.request.url)]
    assert matching, "sign-in did not verify the staff member"
    headers = matching[-1].request.headers
    assert "x-api-key" not in headers
    scheme, _, token = headers["authorization"].partition(" ")
    assert scheme == "Bearer"
    claims = verify_token(token)
    assert claims["is_service_account"] is True
    assert claims["tenant_id"] == os.environ.get("TENANT_ID")
    assert api_key not in token


@pytest.mark.asyncio
async def test_store_lookup_carries_a_terminal_token_not_the_key(http_client, admin_header, mock_outbound_services):
    """Open looks the store name up in the terminal service itself."""
    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    await _post_with_key(http_client, terminal_id, api_key, "sign-in", {"staff_id": "S001"})
    mock_outbound_services.calls.reset()
    await _post_with_key(http_client, terminal_id, api_key, "open", {"initial_amount": 10000.0})

    _assert_carries_terminal_token(mock_outbound_services.calls, ":8001/api/v1/tenants/", terminal_id, api_key)


@pytest.mark.asyncio
async def test_transaction_list_carries_a_terminal_token_not_the_key(http_client, admin_header, mock_outbound_services):
    """Close reads the terminal's transactions from cart."""
    terminal_id, api_key = await _create_terminal(http_client, admin_header)

    await _post_with_key(http_client, terminal_id, api_key, "sign-in", {"staff_id": "S001"})
    await _post_with_key(http_client, terminal_id, api_key, "open", {"initial_amount": 10000.0})
    mock_outbound_services.calls.reset()
    await _post_with_key(http_client, terminal_id, api_key, "close", {"physical_amount": 10000.0})

    _assert_carries_terminal_token(mock_outbound_services.calls, "/transactions", terminal_id, api_key)


@pytest.mark.asyncio
async def test_a_terminal_write_in_flight_does_not_undo_a_reissue(http_client, admin_header, mock_outbound_services):
    """Sign-in, open and close read the terminal, work, then write it back. A
    reissue landing in between must survive that write (issue #136)."""
    from kugel_common.database import database as db_helper

    from app.config.settings import settings
    from app.models.repositories.terminal_info_repository import TerminalInfoRepository

    terminal_id, old_key = await _create_terminal(http_client, admin_header)
    tenant_id = os.environ.get("TENANT_ID")
    repo = TerminalInfoRepository(await db_helper.get_db_async(f"{settings.DB_NAME_PREFIX}_{tenant_id}"), tenant_id)

    in_flight = await repo.get_terminal_info_by_id_async(terminal_id)  # read before the reissue
    response = await http_client.post(f"/api/v1/terminals/{terminal_id}/api-key", headers=admin_header)
    new_key = response.json()["data"]["apiKey"]
    in_flight.description = "written after the reissue"
    await repo.replace_terminal_info_async(terminal_id, in_flight)

    stored = await (await _terminal_collection()).find_one({"terminal_id": terminal_id})
    assert stored["description"] == "written after the reissue"
    assert stored["api_key_hash"] == hash_api_key(new_key)
    assert await _token_status(http_client, new_key, terminal_id) == status.HTTP_200_OK
    assert await _token_status(http_client, old_key, terminal_id) == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_another_tenants_terminal_cannot_be_reissued(http_client, admin_header, mock_outbound_services):
    from datetime import datetime, timedelta, timezone

    import jwt

    from kugel_common.config.settings import settings

    terminal_id, api_key = await _create_terminal(http_client, admin_header)
    other_tenant = jwt.encode(
        {"sub": "admin", "tenant_id": "OTHER1", "is_superuser": True,
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/api-key", headers={"Authorization": f"Bearer {other_tenant}"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert await _token_status(http_client, api_key, terminal_id) == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_a_plaintext_left_beside_a_digest_is_swept(http_client, admin_header, mock_outbound_services):
    from app.database import database_setup

    terminal_id, api_key = await _create_terminal(http_client, admin_header)
    collection = await _terminal_collection()
    await collection.update_one({"terminal_id": terminal_id}, {"$set": {"api_key": "leftover-plaintext"}})

    await database_setup.seal_plaintext_api_keys(os.environ.get("TENANT_ID"))

    stored = await collection.find_one({"terminal_id": terminal_id})
    assert "api_key" not in stored
    assert stored["api_key_hash"] == hash_api_key(api_key)
    assert await _token_status(http_client, api_key, terminal_id) == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_with_sealing_off_a_legacy_terminal_is_verified_and_left_as_it_is(
    http_client, admin_header, mock_outbound_services, monkeypatch
):
    """SEAL_LEGACY_TERMINAL_API_KEYS=false keeps a rollback open: a plaintext
    record still authenticates, and neither verification nor setup seals it."""
    from kugel_common.config.settings import settings as common_settings

    from app.config.settings import settings as app_settings
    from app.database import database_setup

    monkeypatch.setattr(common_settings, "SEAL_LEGACY_TERMINAL_API_KEYS", False)
    monkeypatch.setattr(app_settings, "SEAL_LEGACY_TERMINAL_API_KEYS", False)
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    legacy_key = f"kept-{terminal_id}-0123456789"
    await _plant_legacy_terminal(terminal_id, legacy_key)

    assert await _token_status(http_client, legacy_key, terminal_id) == status.HTTP_200_OK
    assert await _token_status(http_client, legacy_key) == status.HTTP_200_OK
    await database_setup.seal_plaintext_api_keys(os.environ.get("TENANT_ID"))

    stored = await (await _terminal_collection()).find_one({"terminal_id": terminal_id})
    assert stored["api_key"] == legacy_key
    assert "api_key_hash" not in stored

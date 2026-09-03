# Copyright 2026 masa@kugel
"""No credential may be readable in anything the system wrote down (issue #211).

Every other check for this is a proxy - does the call look right, is the type
in the masked set, did a reviewer see it. This one tests the property itself:
plant credentials that could not be anything else, use the system the way a
store does, then read back every log and every collection and look for them.

That difference is not academic. Five review rounds and three static sweeps
missed `f"...{staff_master_repo.terminal_info}"`, because it is an attribute
rather than a bare name and its `logger.debug(` is on the line above - two
assumptions every grep had made. This found it on the first run, because it
assumes nothing about how the value got written, only that it must not appear.

Two kinds of sentinel, and the second matters more:

- **planted** - values sent in (a staff PIN, an account password), distinctive
  enough that a hit is certainly ours rather than a coincidence. "1234" would
  be useless here.
- **issued** - values the server generates and hands back: the terminal's
  api_key, the JWTs. These are the credentials that actually guard something.

What this cannot do is speak for paths it did not run, which is why the
failure paths below are provoked on purpose - a duplicate create, a rejected
type, a wrong api_key. Those are where the last two leaks were found.
"""

import json
import os
import subprocess
import uuid

import httpx
import pytest

pytestmark = pytest.mark.e2e

STORE = "9001"
TERMINAL_NO = 1
ITEM = "ITEM-SENTINEL"

# Values a log could not contain by chance.
PLANTED = {
    "staff pin": "PIN-SENTINEL-7f3a91",
    "account password": "PW-SENTINEL-4c8b20",
    "updated staff pin": "PIN-SENTINEL-updated-2e6d",
}

# The only two collections that hold a credential by design rather than by
# accident: the terminal master IS where the api_key lives (`security.py`
# compares against it) and the staff master IS where the pin lives. Finding
# them there is not a leak; finding them anywhere else is - including in the
# tenant and store masters, which carry no credential and so must stay in
# scope rather than be waved through.
CREDENTIAL_OF_RECORD = ("info_terminal", "master_staff")


def _client(url_env: str) -> httpx.Client:
    return httpx.Client(base_url=os.environ[url_env], timeout=30.0)


def _try(label: str, fn):
    """Run a step; a failure is reported but does not stop the walk.

    The point is to reach as many code paths as possible, and one endpoint
    refusing (a store that already exists, say) must not cost us the rest.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - the walk continues regardless
        print(f"    (step '{label}' did not complete: {type(exc).__name__}: {exc})")
        return None


def _exercise(tenant_id: str) -> dict:
    """Use the system as a store does, then break it on purpose.

    Returns the credentials the server issued along the way.
    """
    issued: dict[str, str] = {}

    with _client("URL_ACCOUNT") as c:
        c.post("/api/v1/accounts/register", json={
            "username": "admin", "password": PLANTED["account password"], "tenant_id": tenant_id})
        resp = c.post("/api/v1/accounts/token", data={
            "username": "admin", "password": PLANTED["account password"], "client_id": tenant_id})
        resp.raise_for_status()
        issued["admin jwt"] = resp.json()["access_token"]
    h = {"Authorization": f"Bearer {issued['admin jwt']}"}

    with _client("URL_TERMINAL") as t:
        _try("tenant", lambda: t.post("/api/v1/tenants", headers=h, json={
            "tenant_id": tenant_id, "tenant_name": "Sentinel", "stores": [], "tags": []}))
        _try("store", lambda: t.post(f"/api/v1/tenants/{tenant_id}/stores", headers=h, json={
            "store_code": STORE, "store_name": "Sentinel Store", "tags": []}))

    with _client("URL_MASTER_DATA") as m:
        base = f"/api/v1/tenants/{tenant_id}"
        # The pin travels in the request and comes back in the response.
        _try("staff create", lambda: m.post(f"{base}/staff", headers=h, json={
            "id": "S001", "name": "Sentinel Staff", "pin": PLANTED["staff pin"], "roles": ["staff"]}))
        _try("staff read", lambda: m.get(f"{base}/staff/S001", headers=h))
        _try("staff list", lambda: m.get(f"{base}/staff", headers=h))
        _try("staff update", lambda: m.put(f"{base}/staff/S001", headers=h, json={
            "name": "Sentinel Staff", "pin": PLANTED["updated staff pin"], "roles": ["staff"]}))
        # Failure path: the same id again. CannotCreateException puts the
        # document into its message, and the handler returns that message.
        _try("duplicate staff", lambda: m.post(f"{base}/staff", headers=h, json={
            "id": "S001", "name": "Dup", "pin": PLANTED["staff pin"], "roles": ["staff"]}))
        # Failure path: a 422, whose detail echoes the value it rejected.
        _try("rejected staff", lambda: m.post(f"{base}/staff", headers=h, json={
            "id": "S002", "name": "Bad", "pin": {"nested": PLANTED["staff pin"]}, "roles": ["staff"]}))

        _try("category", lambda: m.post(f"{base}/categories", headers=h, json={
            "categoryCode": "001", "description": "C", "descriptionShort": "C", "taxCode": "01"}))
        _try("item", lambda: m.post(f"{base}/items", headers=h, json={
            "itemCode": ITEM, "description": "I", "unitPrice": 100.0, "unitCost": 50.0,
            "taxCode": "01", "categoryCode": "001", "itemDetails": [], "imageUrls": []}))
        _try("item-store", lambda: m.post(f"{base}/stores/{STORE}/items", headers=h, json={
            "itemCode": ITEM, "storePrice": 100.0}))
        _try("payment", lambda: m.post(f"{base}/payments", headers=h, json={
            "paymentCode": "01", "description": "Cash", "limitAmount": 0.0, "canRefund": True,
            "canDepositOver": True, "canChange": True, "isActive": True}))

    # The api_key is ISSUED here - the credential that actually guards the API.
    with _client("URL_TERMINAL") as t:
        resp = t.post("/api/v1/terminals", headers=h, json={
            "store_code": STORE, "terminal_no": TERMINAL_NO, "description": "Sentinel Terminal"})
        assert resp.status_code == 201, f"terminal create -> {resp.status_code}: {resp.text}"
        data = resp.json()["data"]
        terminal_id = data["terminalId"]
        issued["api key"] = data["apiKey"]

        resp = t.post(f"/api/v1/auth/token?terminal_id={terminal_id}",
                      headers={"X-API-KEY": issued["api key"]})
        issued["terminal jwt"] = resp.json()["data"]["access_token"]

        tj = {"Authorization": f"Bearer {issued['terminal jwt']}"}
        resp = t.post(f"/api/v1/terminals/{terminal_id}/sign-in",
                      json={"staff_id": "S001"}, headers=tj)
        tj = {"Authorization": f"Bearer {resp.headers.get('x-new-token', issued['terminal jwt'])}"}
        resp = t.post(f"/api/v1/terminals/{terminal_id}/open",
                      json={"initial_amount": 0.0}, headers=tj)
        tj = {"Authorization": f"Bearer {resp.headers.get('x-new-token', issued['terminal jwt'])}"}
        _try("cash-in", lambda: t.post(f"/api/v1/terminals/{terminal_id}/cash-in",
                                       json={"amount": 1000.0, "description": "sentinel"}, headers=tj))

    ak = {"X-API-KEY": issued["api key"]}
    with _client("URL_CART") as k:
        resp = k.post(f"/api/v1/carts?terminal_id={terminal_id}", headers=ak, json={
            "tenant_id": tenant_id, "terminal_id": terminal_id,
            "operator_code": "S001", "operator_name": "Sentinel Staff"})
        if resp.status_code == 201:
            cart_id = resp.json()["data"]["cartId"]
            base = f"/api/v1/carts/{cart_id}"
            k.post(f"{base}/lineItems?terminal_id={terminal_id}", headers=ak,
                   json=[{"itemCode": ITEM, "quantity": 1}])
            k.post(f"{base}/subtotal?terminal_id={terminal_id}", headers=ak)
            k.post(f"{base}/payments?terminal_id={terminal_id}", headers=ak,
                   json=[{"paymentCode": "01", "amount": 100.0}])
            k.post(f"{base}/bill?terminal_id={terminal_id}", headers=ak)

    # Closing publishes the open/close log to journal and report, which store
    # it. That log embeds a whole terminal document.
    with _client("URL_TERMINAL") as t:
        _try("close", lambda: t.post(f"/api/v1/terminals/{terminal_id}/close", json={}, headers=tj))

    with _client("URL_MASTER_DATA") as m:
        # The delete path reads the record before removing it.
        _try("staff delete", lambda: m.delete(f"/api/v1/tenants/{tenant_id}/staff/S001", headers=h))

    with _client("URL_CART") as k:
        # And an authentication failure, so that path is walked too.
        _try("wrong api key", lambda: k.post(
            f"/api/v1/carts?terminal_id={terminal_id}",
            headers={"X-API-KEY": "SENTINEL-WRONG-KEY-000"},
            json={"tenant_id": tenant_id, "terminal_id": terminal_id,
                  "operator_code": "S001", "operator_name": "x"}))

    return issued


def _scan_container_logs(sentinels: dict) -> list:
    """Look through every running container's log. Skipped if docker is not usable."""
    try:
        names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                               capture_output=True, text=True, timeout=30).stdout.split()
    except Exception:
        pytest.skip("docker is not available to read container logs")
    if not names:
        pytest.skip("no running containers to read logs from")

    hits = []
    for name in sorted(names):
        try:
            out = subprocess.run(["docker", "logs", "--tail", "200000", name],
                                 capture_output=True, text=True, timeout=180)
        except Exception:
            continue
        text = out.stdout + out.stderr
        for label, value in sentinels.items():
            if value and value in text:
                excerpt = next((ln.strip() for ln in text.split("\n") if value in ln), "")
                hits.append(f"{name}: {label} -> {excerpt[:200]}")
    return hits


def _mongo():
    pymongo = pytest.importorskip("pymongo", reason="pymongo is needed to scan the databases")
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true")
    return pymongo.MongoClient(uri, serverSelectionTimeoutMS=10000)


def _await_the_fanout(tenant_id: str, wait_for) -> None:
    """Wait until the open/close log has reached journal and report for real."""
    client = _mongo()

    def arrived():
        return all(
            "log_open_close" in client[f"db_{service}_{tenant_id}"].list_collection_names()
            and client[f"db_{service}_{tenant_id}"]["log_open_close"].count_documents({}) > 0
            for service in ("journal", "report")
        )

    wait_for(arrived, timeout=30.0, interval=0.5,
             description="the open/close log reaching journal and report")


def _scan_mongo(sentinels: dict, tenant_id: str) -> tuple:
    """Look through every collection, except the ones that hold the value by design.

    Newest first, because a shared collection - `db_*_commons.log_request` -
    accumulates across every run this machine has ever done, and reading an
    arbitrary 3000 of those can miss the ones this run just wrote.

    Returns (records seen from this run, hits).
    """
    client = _mongo()

    seen_from_this_run = 0
    hits = []
    for db_name in client.list_database_names():
        if db_name in ("admin", "config", "local"):
            continue
        db = client[db_name]
        for coll_name in db.list_collection_names():
            if coll_name in CREDENTIAL_OF_RECORD:
                continue
            docs = list(db[coll_name].find({}, limit=3000).sort("_id", -1))
            blob = json.dumps(docs, default=str, ensure_ascii=False)
            if tenant_id in db_name or tenant_id in blob:
                seen_from_this_run += len(docs)
            for label, value in sentinels.items():
                if value and value in blob:
                    hits.append(f"{db_name}.{coll_name}: {label}")
    return seen_from_this_run, hits


def test_no_credential_is_readable_in_anything_written_down(wait_for):
    tenant_id = "S" + uuid.uuid4().hex[:3].upper()
    issued = _exercise(tenant_id)

    sentinels = dict(PLANTED)
    sentinels.update(issued)
    assert "api key" in sentinels, "precondition: the terminal never issued an api_key"

    # The open/close log reaches journal and report through Dapr, and it is the
    # document that embeds a whole terminal - so scanning before it lands is
    # how this test passes for the wrong reason. It has already happened once:
    # an earlier run reported journal and report clean while their collections
    # held nothing at all, because the Dapr sidecars were not up.
    _await_the_fanout(tenant_id, wait_for)

    scanned, hits = _scan_mongo(sentinels, tenant_id)
    hits += _scan_container_logs(sentinels)

    # A scan that looked at nothing proves nothing. This run's own records must
    # be among what was read, or the result below is an accident.
    assert scanned > 0, "the scan did not see a single record from this run"

    assert hits == [], "a credential is readable in:\n  " + "\n  ".join(hits)

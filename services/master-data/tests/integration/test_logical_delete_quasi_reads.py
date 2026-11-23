"""The reads cart and others use for sale skip deleted records (issue #324).

These take no include_deleted: the item store detail, the active promotions
(every path: none, by store, by category, by both) and a setting's value.
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest

from kugel_common.database import database as db_helper

from tests.integration.logical_delete_masters import STORE, base

pytestmark = pytest.mark.asyncio


def _code(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6].upper()}"


async def _item(http_client, header, code):
    r = await http_client.post(
        f"{base()}/items",
        json={"itemCode": code, "description": "Common", "unitPrice": 100, "unitCost": 50, "itemDetails": [],
              "imageUrls": [], "categoryCode": "001", "taxCode": "01"},
        headers=header,
    )
    assert r.status_code == 201, r.text


async def test_the_detail_of_a_deleted_item_is_not_found(http_client, admin_header):
    code = _code("QI")
    await _item(http_client, admin_header, code)
    r = await http_client.post(f"{base()}/stores/{STORE}/items", json={"itemCode": code, "storePrice": 80.0}, headers=admin_header)
    assert r.status_code == 201, r.text
    assert (await http_client.delete(f"{base()}/items/{code}", headers=admin_header)).status_code == 200

    r = await http_client.get(f"{base()}/stores/{STORE}/items/{code}/details", headers=admin_header)

    assert r.status_code == 404, r.text


async def test_a_deleted_store_record_leaves_the_common_values(http_client, admin_header):
    code = _code("QS")
    await _item(http_client, admin_header, code)
    r = await http_client.post(f"{base()}/stores/{STORE}/items", json={"itemCode": code, "storePrice": 80.0}, headers=admin_header)
    assert r.status_code == 201, r.text
    assert (await http_client.delete(f"{base()}/stores/{STORE}/items/{code}", headers=admin_header)).status_code == 200

    r = await http_client.get(f"{base()}/stores/{STORE}/items/{code}/details", headers=admin_header)

    assert r.status_code == 200, r.text
    assert r.json()["data"]["storePrice"] is None
    assert r.json()["data"]["unitPrice"] == 100


async def _promotion(http_client, header, code, category):
    now = datetime.now()
    r = await http_client.post(
        f"{base()}/promotions",
        json={
            "promotionCode": code, "promotionType": "category_discount", "name": code, "description": code,
            "startDatetime": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
            "endDatetime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
            "isActive": True,
            "detail": {"targetStoreCodes": [STORE], "targetCategoryCodes": [category], "discountRate": 5.0},
        },
        headers=header,
    )
    assert r.status_code == 201, r.text


@pytest.mark.parametrize(
    "params",
    [{}, {"storeCode": STORE}, {"categoryCode": "CAT"}, {"storeCode": STORE, "categoryCode": "CAT"}],
    ids=["all", "store", "category", "store-and-category"],
)
async def test_active_promotions_skip_deleted_ones_and_keep_ones_without_the_field(http_client, admin_header, params):
    category = _code("QC")
    query = {k: (category if k == "categoryCode" else v) for k, v in params.items()}
    deleted, legacy, live = _code("QD"), _code("QL"), _code("QV")
    for code in (deleted, legacy, live):
        await _promotion(http_client, admin_header, code, category)
    assert (await http_client.delete(f"{base()}/promotions/{deleted}", headers=admin_header)).status_code == 200
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    await db["master_promotion"].update_one({"promotion_code": legacy}, {"$unset": {"is_deleted": ""}})

    r = await http_client.get(f"{base()}/promotions/active", params=query, headers=admin_header)

    assert r.status_code == 200, r.text
    codes = {p["promotionCode"] for p in r.json()["data"]}
    assert deleted not in codes
    assert {legacy, live} <= codes


async def test_the_value_of_a_deleted_setting_is_not_found(http_client, admin_header):
    name = _code("QSET")
    r = await http_client.post(f"{base()}/settings", json={"name": name, "defaultValue": "x", "values": []}, headers=admin_header)
    assert r.status_code == 201, r.text
    assert (await http_client.delete(f"{base()}/settings/{name}", headers=admin_header)).status_code == 200

    r = await http_client.get(
        f"{base()}/settings/{name}/value", params={"store_code": STORE, "terminal_no": 1}, headers=admin_header
    )

    assert r.status_code == 404, r.text

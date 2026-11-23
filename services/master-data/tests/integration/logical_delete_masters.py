"""How to drive each deletable master through the API, for the logical-delete tests (issue #324).

Each Master knows its paths, how to build a create and an update body for a
code, which response field carries the code, and which collection it lives in.
Item store records need an item common record first; item books get their id
from the server.
"""

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

STORE = "5678"


def _tenant() -> str:
    return os.environ.get("TENANT_ID")


def base() -> str:
    return f"/api/v1/tenants/{_tenant()}"


def _promotion_window() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%Y-%m-%dT%H:%M:%S"), (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class Master:
    name: str
    collection: str
    collection_path: str  # relative to base()
    code_field: str  # camelCase field in the response that carries the key
    key_field: str  # snake_case field in the stored document
    create_body: Callable[[str, str], dict]  # (code, label) -> body
    update_body: Callable[[str, str], dict]  # (code, label) -> body
    label_field: str  # camelCase field that shows the label back
    generated_id: bool = False
    needs_item_common: bool = False
    list_params: dict = field(default_factory=lambda: {"limit": 1000})

    def new_code(self) -> str:
        return f"LD{uuid.uuid4().hex[:8].upper()}"

    def item_path(self, code: str) -> str:
        return f"{base()}{self.collection_path}/{code}"

    def list_path(self) -> str:
        return f"{base()}{self.collection_path}"


def _settings_body(code: str, label: str) -> dict:
    return {"name": code, "defaultValue": label, "values": []}


def _promotion_body(code: str, label: str) -> dict:
    start, end = _promotion_window()
    return {
        "promotionCode": code,
        "promotionType": "category_discount",
        "name": label,
        "description": label,
        "startDatetime": start,
        "endDatetime": end,
        "isActive": True,
        "detail": {"targetStoreCodes": [STORE], "targetCategoryCodes": ["LDCAT"], "discountRate": 10.0},
    }


def _promotion_update(code: str, label: str) -> dict:
    body = _promotion_body(code, label)
    body.pop("promotionCode")
    body.pop("promotionType")
    return body


def _item_body(code: str, label: str) -> dict:
    return {
        "itemCode": code,
        "description": label,
        "unitPrice": 100,
        "unitCost": 50,
        "itemDetails": [],
        "imageUrls": [],
        "categoryCode": "001",
        "taxCode": "01",
    }


MASTERS = [
    Master(
        "category", "master_category", "/categories", "categoryCode", "category_code",
        lambda c, l: {"categoryCode": c, "description": l, "descriptionShort": l[:10], "taxCode": "01"},
        lambda c, l: {"categoryCode": c, "description": l, "descriptionShort": l[:10], "taxCode": "01"},
        "description",
    ),
    Master(
        "item_common", "master_item_common", "/items", "itemCode", "item_code",
        _item_body,
        lambda c, l: {k: v for k, v in _item_body(c, l).items() if k != "itemCode"},
        "description",
    ),
    Master(
        "item_store", "master_item_store", f"/stores/{STORE}/items", "itemCode", "item_code",
        lambda c, l: {"itemCode": c, "storePrice": float(len(l))},
        lambda c, l: {"storePrice": float(len(l))},
        "storePrice",
        needs_item_common=True,
    ),
    Master(
        "item_book", "master_item_book", "/item_books", "itemBookId", "item_book_id",
        lambda c, l: {"title": l, "categories": []},
        lambda c, l: {"title": l},
        "title",
        generated_id=True,
    ),
    Master(
        "payment", "master_payment", "/payments", "paymentCode", "payment_code",
        lambda c, l: {"paymentCode": c, "description": l, "limitAmount": 0.0, "canRefund": True,
                      "canDepositOver": False, "canChange": False, "isActive": True},
        lambda c, l: {"description": l, "limitAmount": 0.0, "canRefund": True, "canDepositOver": False,
                      "canChange": False, "isActive": True},
        "description",
    ),
    Master(
        "promotion", "master_promotion", "/promotions", "promotionCode", "promotion_code",
        _promotion_body, _promotion_update, "name",
    ),
    Master(
        "settings", "master_settings", "/settings", "name", "name",
        _settings_body,
        lambda c, l: {"name": c, "defaultValue": l, "values": []},
        "defaultValue",
    ),
    Master(
        "staff", "master_staff", "/staff", "id", "id",
        lambda c, l: {"id": c, "name": l, "roles": ["staff"]},
        lambda c, l: {"name": l, "roles": ["staff"]},
        "name",
    ),
]

RESTORABLE = [m for m in MASTERS if not m.generated_id]


def master_ids(masters) -> list[str]:
    return [m.name for m in masters]


async def create(http_client, header, master: Master, code: Optional[str] = None, label: str = "Old"):
    """Create a record and return (code, response)."""
    code = code or master.new_code()
    if master.needs_item_common:
        r = await http_client.post(f"{base()}/items", json=_item_body(code, "Common"), headers=header)
        assert r.status_code in (201, 400), r.text
    r = await http_client.post(master.list_path(), json=master.create_body(code, label), headers=header)
    if master.generated_id and r.status_code == 201:
        code = r.json()["data"][master.code_field]
    return code, r


def list_codes(response, master: Master) -> list[str]:
    return [row.get(master.code_field) for row in response.json().get("data") or []]

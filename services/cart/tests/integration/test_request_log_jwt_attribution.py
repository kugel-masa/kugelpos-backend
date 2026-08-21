# Copyright 2026 masa@kugel
"""What a terminal-JWT request leaves in the request log (issue #181).

Here rather than in `services/commons` because that package is unit-only by
design, and what matters is the row that reaches MongoDB. The commons tests prove
the middleware builds the right document; this proves it is stored, through a
real service and a real collection.

The token used is the suite's existing `terminal_jwt` fixture, which carries no
`open_counter` claim - the shape a terminal has before it is ever opened. That
was not deliberate on its part, but it is the case worth running against a real
stack: an absent claim reaching a required field raises inside the middleware's
`finally`, where the cost is not a missing field but the route's response.
"""

import os

import pytest
from kugel_common.middleware.request_log_buffer import get_request_log_buffer

pytestmark = pytest.mark.asyncio


async def _logged(url_fragment):
    """Flush the request-log buffer, then read back the row for this request."""
    from kugel_common.database import database as db_helper

    await get_request_log_buffer().shutdown()
    db = await db_helper.get_db_async(f"{os.environ.get('DB_NAME_PREFIX')}_{os.environ.get('TENANT_ID')}")
    return await db["log_request"].find_one(
        {"request_info.url": {"$regex": url_fragment}}, sort=[("request_info.accept_time", -1)]
    )


async def test_a_jwt_request_records_the_store_and_terminal(http_client, terminal_jwt):
    """Before #181 this row named no store, no terminal and no staff.

    The request itself is refused - the fixture's terminal is Idle, not opened -
    which is the point: a refusal is what an audit trail most needs to attribute,
    and it is refused on the route's own terms rather than by the logger.
    """
    response = await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "99", "user_name": "JWT Attribution"},
        headers={"Authorization": f"Bearer {terminal_jwt}"},
    )

    assert response.status_code != 500, (
        "the logging middleware replaced the route's response - "
        f"an absent claim reached a required field ({response.text[:200]})"
    )

    row = await _logged("/api/v1/carts")
    assert row is not None, "the request was not logged at all"
    info = row["terminal_info"]
    assert (info["store_code"], info["terminal_no"]) == ("5678", 9), f"no terminal attribution recorded: {info}"
    assert row["tenant_id"] == os.environ.get("TENANT_ID")


async def test_an_unopened_terminal_still_gets_a_business_date_field(http_client, terminal_jwt):
    """The claims a terminal does not have yet are absent, not empty.

    They still have to arrive as the collection's types, or the row is never
    written - and the failure lands on the route, not on the log.
    """
    await http_client.post(
        "/api/v1/carts",
        json={"transaction_type": 101, "user_id": "99", "user_name": "JWT Attribution"},
        headers={"Authorization": f"Bearer {terminal_jwt}"},
    )

    row = await _logged("/api/v1/carts")

    assert row is not None
    assert row["terminal_info"]["business_date"] == ""
    assert row["terminal_info"]["open_counter"] == 0

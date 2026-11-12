# Copyright 2026 masa@kugel
"""A terminal deleted and registered again can open again the same day.

The open/close log was unique on (business_date, open_counter, operation), and
open_counter restarts at 1 when a terminal is registered again. Reopening that
day collided with the previous registration's open log. The open runs inside a
transaction, MongoDB aborts it on E11000, and the replace that followed as
"recovery" then failed too, so the open was refused until the next day.

The log is now unique on (business_counter, operation). business_counter is
carried by the terminal across the re-registration and never reused.
"""

import jwt
import pytest
from fastapi import status

from tests.integration.test_terminal_lifecycle import _create_terminal, _signin

TERMINAL_NO = 90


async def _open(http_client, header, terminal_id, **body):
    return await http_client.post(
        f"/api/v1/terminals/{terminal_id}/open", json={"initial_amount": 1000.0, **body}, headers=header
    )


async def _close(http_client, header, terminal_id):
    response = await http_client.post(
        f"/api/v1/terminals/{terminal_id}/close", json={"physical_amount": 1000.0}, headers=header
    )
    assert response.status_code == status.HTTP_200_OK, response.text


def _claims(response):
    from kugel_common.config.settings import settings

    return jwt.decode(response.headers["x-new-token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


@pytest.mark.asyncio
async def test_a_reregistered_terminal_opens_again_the_same_day(http_client, admin_header, mock_outbound_services):
    from tests.integration import test_terminal_lifecycle as lifecycle

    lifecycle._TERMINAL_NO_COUNTER[0] = TERMINAL_NO
    terminal_id, _ = await _create_terminal(http_client, admin_header)
    await _signin(http_client, admin_header, terminal_id)
    first = await _open(http_client, admin_header, terminal_id)
    assert first.status_code == status.HTTP_200_OK, first.text
    carried = _claims(first)
    await _close(http_client, admin_header, terminal_id)

    response = await http_client.delete(f"/api/v1/terminals/{terminal_id}", headers=admin_header)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Registered again under the same terminal number: open_counter starts over.
    lifecycle._TERMINAL_NO_COUNTER[0] = TERMINAL_NO
    again_id, _ = await _create_terminal(http_client, admin_header)
    assert again_id == terminal_id
    await _signin(http_client, admin_header, terminal_id)

    # The terminal presents the counters it carried from its previous token.
    second = await _open(http_client, admin_header, terminal_id, business_counter=carried["business_counter"])

    assert second.status_code == status.HTTP_200_OK, second.text
    reopened = _claims(second)
    assert reopened["business_date"] == carried["business_date"]
    assert reopened["open_counter"] == carried["open_counter"], "open_counter restarted, as before"
    assert reopened["business_counter"] > carried["business_counter"], "a new business, never reused"

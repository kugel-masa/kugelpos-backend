"""StaffMasterService.verify_staff_async decides whether a staff member may sign in (issue #323).

The PIN is required only when the staff record has one. The comparison happens
here and nowhere else, and the PIN never reaches a message or a log line.
"""

import logging
from unittest.mock import AsyncMock

import pytest

from app.exceptions import (
    StaffVerifyPinMismatchException,
    StaffVerifyPinRequiredException,
    StaffVerifyStaffNotFoundException,
)
from app.models.documents.staff_master_document import StaffMasterDocument
from app.services.staff_master_service import StaffMasterService

PIN = "pin-sentinel-7c1e9a"
WRONG = "pin-wrong-3f80b2"


def _service(staff):
    repo = AsyncMock()
    repo.get_staff_by_id_async.return_value = staff
    return StaffMasterService(repo), repo


def _staff(pin):
    return StaffMasterDocument(tenant_id="T1", id="S1", name="Ann", pin=pin, roles=["cashier"])


@pytest.mark.asyncio
async def test_a_missing_staff_member_is_not_found():
    service, repo = _service(None)

    with pytest.raises(StaffVerifyStaffNotFoundException):
        await service.verify_staff_async("S1", PIN)

    repo.get_staff_by_id_async.assert_awaited_once_with("S1")


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", [None, ""])
@pytest.mark.parametrize("given", [None, "", PIN, WRONG])
async def test_a_staff_member_without_a_pin_passes_whatever_is_sent(stored, given):
    service, _ = _service(_staff(stored))

    staff = await service.verify_staff_async("S1", given)

    assert staff.id == "S1"


@pytest.mark.asyncio
@pytest.mark.parametrize("given", [None, ""])
async def test_a_staff_member_with_a_pin_needs_one(given):
    service, _ = _service(_staff(PIN))

    with pytest.raises(StaffVerifyPinRequiredException):
        await service.verify_staff_async("S1", given)


@pytest.mark.asyncio
async def test_a_wrong_pin_is_refused():
    service, _ = _service(_staff(PIN))

    with pytest.raises(StaffVerifyPinMismatchException):
        await service.verify_staff_async("S1", WRONG)


@pytest.mark.asyncio
async def test_the_right_pin_passes():
    service, _ = _service(_staff(PIN))

    staff = await service.verify_staff_async("S1", PIN)

    assert staff.id == "S1"
    assert staff.name == "Ann"


@pytest.mark.asyncio
async def test_a_blank_stored_pin_is_a_pin_and_is_compared_as_is():
    service, _ = _service(_staff(" "))

    assert (await service.verify_staff_async("S1", " ")).id == "S1"
    with pytest.raises(StaffVerifyPinRequiredException):
        await service.verify_staff_async("S1", "")
    with pytest.raises(StaffVerifyPinMismatchException):
        await service.verify_staff_async("S1", "  ")


@pytest.mark.asyncio
@pytest.mark.parametrize("stored, given", [("１２３４", "１２３４"), ("pïn", "pïn"), ("１２３４", "1234")])
async def test_a_non_ascii_pin_is_compared_without_error(stored, given):
    service, _ = _service(_staff(stored))

    if stored == given:
        assert (await service.verify_staff_async("S1", given)).id == "S1"
    else:
        with pytest.raises(StaffVerifyPinMismatchException):
            await service.verify_staff_async("S1", given)


@pytest.mark.asyncio
async def test_no_message_or_log_line_carries_the_pin(caplog):
    caplog.set_level(logging.DEBUG)
    failures = []
    for stored, given in ((PIN, WRONG), (PIN, None), (None, PIN)):
        service, _ = _service(_staff(stored) if stored or given else None)
        try:
            await service.verify_staff_async("S1", given)
        except Exception as e:  # noqa: BLE001 - collecting the messages
            failures.append(f"{e} {getattr(e, 'message', '')} {getattr(e, 'log_message', '')}")
    service, _ = _service(None)
    try:
        await service.verify_staff_async("S1", PIN)
    except StaffVerifyStaffNotFoundException as e:
        failures.append(f"{e} {e.message} {e.log_message}")

    text = "\n".join(failures + [r.getMessage() for r in caplog.records])
    assert PIN not in text
    assert WRONG not in text

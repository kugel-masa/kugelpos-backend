"""Terminal sign-in verifies the staff member through master-data (issue #323).

- US1: a staff member with a PIN signs in only with the right PIN
- US2: a staff member without one signs in with their ID alone
- US3: the three failures answer the same; the reason goes to the log only
- US4: master-data being unreachable is not an authentication failure
"""

import logging
from unittest.mock import AsyncMock

import pytest

from kugel_common.enums import StaffAuthenticationFailure
from kugel_common.exceptions import RepositoryException, StaffAuthenticationException
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.utils.http_client_helper import ServiceUrlNotConfiguredError

from app.enums.terminal_status import TerminalStatus
from app.exceptions import (
    ExternalServiceException,
    SignInOutException,
    TerminalAlreadySignedInException,
)
from app.models.documents.terminal_info_document import TerminalInfoDocument
from app.services.terminal_service import TerminalService

PIN = "pin-sentinel-7c1e9a"
WRONG = "pin-wrong-3f80b2"


def _terminal(staff=None):
    t = TerminalInfoDocument()
    t.tenant_id = "T1"
    t.terminal_id = "T1-S001-1"
    t.store_code = "S001"
    t.terminal_no = 1
    t.status = TerminalStatus.Idle.value
    t.staff = staff
    return t


def _service(verify=None, terminal=None):
    repos = {
        "terminal_info_repo": AsyncMock(),
        "staff_master_repo": AsyncMock(),
        "store_info_repo": AsyncMock(),
        "cash_in_out_log_repo": AsyncMock(),
        "open_close_log_repo": AsyncMock(),
        "settlement_repo": AsyncMock(),
        "terminal_log_delivery_status_repo": AsyncMock(),
    }
    current = terminal or _terminal()
    repos["terminal_info_repo"].get_terminal_info_by_id_async.return_value = current
    if isinstance(verify, BaseException):
        repos["staff_master_repo"].verify_staff_async.side_effect = verify
    else:
        repos["staff_master_repo"].verify_staff_async.return_value = verify or StaffMasterDocument(
            tenant_id="T1", id="S1", name="Ann"
        )
    return TerminalService(terminal_id=current.terminal_id, **repos), repos


def _refused(reason, staff_id="S1"):
    return StaffAuthenticationException(
        message=f"Staff verification refused: staff_id->{staff_id}, reason->{reason.value}", reason=reason
    )


# ---------------------------------------------------------------------------
# US1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_verified_staff_member_is_recorded_without_a_pin():
    service, repos = _service()

    await service.sign_in_terminal_async("S1", PIN)

    repos["staff_master_repo"].verify_staff_async.assert_awaited_once_with("S1", PIN)
    recorded = repos["terminal_info_repo"].replace_terminal_info_async.await_args.args[1]
    assert (recorded.staff.id, recorded.staff.name, recorded.staff.pin) == ("S1", "Ann", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [StaffAuthenticationFailure.PIN_REQUIRED, StaffAuthenticationFailure.PIN_MISMATCH])
async def test_a_refused_pin_leaves_the_terminal_untouched(reason):
    service, repos = _service(verify=_refused(reason))

    with pytest.raises(SignInOutException) as exc_info:
        await service.sign_in_terminal_async("S1", WRONG)

    assert exc_info.value.error_code == "406004"
    assert exc_info.value.status_code == 401
    repos["terminal_info_repo"].replace_terminal_info_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_already_signed_in_terminal_is_refused_before_verifying():
    service, repos = _service(terminal=_terminal(staff=StaffMasterDocument(id="S0", name="Bob")))

    with pytest.raises(TerminalAlreadySignedInException):
        await service.sign_in_terminal_async("S1", PIN)

    repos["staff_master_repo"].verify_staff_async.assert_not_awaited()


@pytest.mark.asyncio
async def test_sign_in_never_fetches_the_staff_without_verifying():
    service, repos = _service()

    await service.sign_in_terminal_async("S1", PIN)

    repos["staff_master_repo"].get_staff_by_id_async.assert_not_called()


# ---------------------------------------------------------------------------
# US2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("pin", [None, "", "anything"])
async def test_the_pin_sent_is_passed_on_as_is(pin):
    service, repos = _service()

    await service.sign_in_terminal_async("S1", pin)

    repos["staff_master_repo"].verify_staff_async.assert_awaited_once_with("S1", pin)
    repos["terminal_info_repo"].replace_terminal_info_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_pin_defaults_to_none():
    service, repos = _service()

    await service.sign_in_terminal_async("S1")

    repos["staff_master_repo"].verify_staff_async.assert_awaited_once_with("S1", None)


# ---------------------------------------------------------------------------
# US3
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_three_failures_answer_the_same_and_log_the_reason(caplog):
    caplog.set_level(logging.WARNING)
    answers = []
    for reason in StaffAuthenticationFailure:
        service, _ = _service(verify=_refused(reason))
        with pytest.raises(SignInOutException) as exc_info:
            await service.sign_in_terminal_async("S1", WRONG)
        e = exc_info.value
        answers.append((e.message, e.error_code, e.user_message, e.status_code))

    assert len(set(answers)) == 1
    assert answers[0][0] == "Staff authentication failed: staff_id->S1"
    logged = "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
    for reason in StaffAuthenticationFailure:
        assert f"reason={reason.value}" in logged
    assert "tenant_id=T1" in logged and "terminal_id=T1-S001-1" in logged and "staff_id=S1" in logged


@pytest.mark.asyncio
async def test_no_log_line_carries_the_pin(caplog):
    caplog.set_level(logging.DEBUG)
    for verify, pin in (
        (None, PIN),
        (_refused(StaffAuthenticationFailure.PIN_MISMATCH), WRONG),
        (RepositoryException("down", "staff web"), PIN),
    ):
        service, _ = _service(verify=verify)
        try:
            await service.sign_in_terminal_async("S1", pin)
        except Exception:  # noqa: BLE001 - only the logs matter here
            pass

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert PIN not in text and WRONG not in text


# ---------------------------------------------------------------------------
# US4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [RepositoryException("Staff verification could not be decided", "staff web"), ServiceUrlNotConfiguredError("master-data", "BASE_URL_MASTER_DATA")],
    ids=["repository", "url-not-configured"],
)
async def test_an_undecided_verification_is_a_dependency_failure(error, caplog):
    caplog.set_level(logging.ERROR)
    service, repos = _service(verify=error)

    with pytest.raises(ExternalServiceException) as exc_info:
        await service.sign_in_terminal_async("S1", PIN)

    assert exc_info.value.error_code == "407201"
    assert exc_info.value.status_code == 502
    repos["terminal_info_repo"].replace_terminal_info_async.assert_not_awaited()
    assert any("could not be decided" in r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)

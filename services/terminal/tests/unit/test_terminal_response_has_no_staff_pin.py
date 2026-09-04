# Copyright 2026 masa@kugel
"""A terminal response must not carry the signed-in staff's PIN (issue #136).

Worse than a single endpoint leaking it: `transform_terminal_info` in commons
reads `staffPin` out of this response and copies it into the caller's
in-memory `TerminalInfoDocument`. So one credential reached every service that
ever asked who was signed in - cart, report, journal - and then whatever each
of them wrote down.
"""

from datetime import datetime

from app.api.common.schemas import BaseStaff
from app.api.common.schemas_transformer import SchemasTransformer
from app.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.models.documents.staff_master_document import StaffMasterDocument

PIN = "PIN-IN-THIS-TEST-4d7a"


def _terminal() -> TerminalInfoDocument:
    return TerminalInfoDocument(
        terminal_id="T0001-5678-9",
        tenant_id="T0001",
        store_code="5678",
        terminal_no=9,
        description="Lane 9",
        function_mode="Sales",
        status="Opened",
        open_counter=1,
        business_counter=1,
        api_key="APIKEY-IN-THIS-TEST-3b7e",
        staff=StaffMasterDocument(id="S001", name="Ann", pin=PIN),
        created_at=datetime(2026, 9, 4),
    )


def test_the_staff_block_has_no_pin_field():
    assert "staff_pin" not in BaseStaff.model_fields, "the response schema can carry the PIN again"


def test_a_transformed_terminal_does_not_carry_the_staff_pin():
    response = SchemasTransformer().transform_terminal(_terminal())

    assert PIN not in str(response.model_dump()), "the staff PIN is in the terminal response"
    # Who is signed in is still answerable.
    assert response.staff.staff_id == "S001"
    assert response.staff.staff_name == "Ann"


def test_the_commons_reader_now_finds_nothing_to_copy():
    # `transform_terminal_info` is what carried it onward. Fed this response,
    # it has no PIN to put into the caller's terminal document.
    from kugel_common.security import transform_terminal_info

    response = SchemasTransformer().transform_terminal(_terminal(), include_api_key=True)
    carried = transform_terminal_info(response.model_dump(by_alias=True))

    assert carried.staff is not None, "precondition: the staff block still arrives"
    assert carried.staff.pin is None, "the PIN still travels between services"
    assert carried.staff.id == "S001"

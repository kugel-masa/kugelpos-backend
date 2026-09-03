# Copyright 2026 masa@kugel
"""A staff response must not carry the PIN (issue #136).

A response is the one place a credential travels to someone who did not
already have it - and from there into their logs, their storage and their
screenshots. Masking the PIN in this service's own logs (issue #211) did
nothing about that; it was still handed out on every read.

The PIN is still accepted on create and update. That is how it gets set, and
the request-log middleware masks it on the way in.
"""

from datetime import datetime

from app.api.common.schemas import BaseStaffCreateRequest, BaseStaffResponse, BaseStaffUpdateRequest
from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.models.documents.staff_master_document import StaffMasterDocument

PIN = "PIN-IN-THIS-TEST-4d7a"


def _staff() -> StaffMasterDocument:
    return StaffMasterDocument(
        id="S001", name="Ann", pin=PIN, roles=["staff"], created_at=datetime(2026, 9, 4)
    )


def test_the_response_schema_has_no_pin_field():
    assert "pin" not in BaseStaffResponse.model_fields, "the response schema can carry the PIN again"


def test_a_transformed_staff_record_does_not_carry_its_pin():
    # The transformer is what fills the response, and it read `staff_doc.pin`.
    response = SchemasTransformerV1().transform_staff(_staff())

    assert PIN not in str(response.model_dump()), "the PIN is in the response"
    # Everything a caller legitimately needs is still there.
    assert response.id == "S001"
    assert response.name == "Ann"
    assert response.roles == ["staff"]


def test_the_pin_is_still_accepted_on_the_way_in():
    # Removing it from the response must not remove the only way to set it.
    assert "pin" in BaseStaffCreateRequest.model_fields
    assert "pin" in BaseStaffUpdateRequest.model_fields


def test_the_document_still_holds_the_pin():
    # This change is about what is handed out, not about how it is stored.
    # Storage is the other half of #136 and stays open.
    assert _staff().pin == PIN

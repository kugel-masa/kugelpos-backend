# Copyright 2026 masa@kugel
"""A request body files what it carries under the tenant, store and terminal of its URL (issue #134).

journal's and report's REST receive endpoints checked the URL's tenant against
the credential, then stored the body's own tenant_id / store_code / terminal_no
as given.
"""

import logging

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from kugel_common.security import bind_body_identity

logger = logging.getLogger(__name__)


class Body(BaseModel):
    tenant_id: str | None = None
    store_code: str | None = None
    terminal_no: int | None = None


def test_a_body_naming_the_urls_identity_is_kept():
    body = Body(tenant_id="T001", store_code="S001", terminal_no=1)

    bind_body_identity(body, "T001", "S001", "1", logger)

    assert body == Body(tenant_id="T001", store_code="S001", terminal_no=1)


def test_a_body_that_leaves_them_out_takes_the_urls():
    body = Body()

    bind_body_identity(body, "T001", "S001", "1", logger)

    assert body == Body(tenant_id="T001", store_code="S001", terminal_no=1)


def test_the_terminal_number_is_compared_as_a_number():
    body = Body(tenant_id="T001", store_code="S001", terminal_no=1)

    bind_body_identity(body, "T001", "S001", "001", logger)

    assert body.terminal_no == 1


@pytest.mark.parametrize(
    "field,value",
    [("tenant_id", "T-OTHER"), ("store_code", "S-OTHER"), ("terminal_no", 9)],
)
def test_a_body_naming_another_is_refused(field, value):
    body = Body(tenant_id="T001", store_code="S001", terminal_no=1)
    setattr(body, field, value)

    with pytest.raises(HTTPException) as raised:
        bind_body_identity(body, "T001", "S001", "1", logger)

    assert raised.value.status_code == 400
    assert field in raised.value.detail


def test_every_field_that_differs_is_named():
    body = Body(tenant_id="T-OTHER", store_code="S-OTHER", terminal_no=9)

    with pytest.raises(HTTPException) as raised:
        bind_body_identity(body, "T001", "S001", "1", logger)

    assert all(field in raised.value.detail for field in ("tenant_id", "store_code", "terminal_no"))


def test_a_url_terminal_that_is_not_a_number_is_refused():
    with pytest.raises(HTTPException) as raised:
        bind_body_identity(Body(), "T001", "S001", "abc", logger)

    assert raised.value.status_code == 400

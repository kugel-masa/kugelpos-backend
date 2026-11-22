"""Request schemas of payment variants (issue #311)."""

import pytest
from pydantic import ValidationError

from app.api.v1.schemas import PaymentVariantCreateRequest, PaymentVariantUpdateRequest


@pytest.mark.parametrize("code", ["VISA", "pay-pay", "gift_01", "a", "A" * 20])
def test_a_code_within_the_pattern_is_taken(code):
    request = PaymentVariantCreateRequest(variant_code=code, name="Name")

    assert request.variant_code == code
    assert request.is_active is True


@pytest.mark.parametrize("code", ["", "A" * 21, "a/b", "a b", "ビザ", "a.b"])
def test_a_code_outside_the_pattern_is_refused(code):
    with pytest.raises(ValidationError):
        PaymentVariantCreateRequest(variant_code=code, name="Name")


@pytest.mark.parametrize("name", ["", "   "])
def test_an_empty_name_is_refused(name):
    with pytest.raises(ValidationError):
        PaymentVariantCreateRequest(variant_code="VISA", name=name)
    with pytest.raises(ValidationError):
        PaymentVariantUpdateRequest(name=name, is_active=True)


def test_the_camel_case_body_is_read():
    request = PaymentVariantCreateRequest.model_validate({"variantCode": "VISA", "name": "VISA", "isActive": False})

    assert request.variant_code == "VISA"
    assert request.is_active is False


def test_an_update_carrying_the_code_is_refused():
    with pytest.raises(ValidationError):
        PaymentVariantUpdateRequest.model_validate({"name": "VISA", "isActive": True, "variantCode": "JCB"})


def test_an_update_needs_both_fields():
    with pytest.raises(ValidationError):
        PaymentVariantUpdateRequest.model_validate({"name": "VISA"})

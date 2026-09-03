# Copyright 2026 masa@kugel
"""Credential masking for logged values (issue #211).

`sanitize_log_body` answers a question about size; these answer a question
about secrecy, and the property under test everywhere here is the same one:
a credential that arrives in a request must not be readable in anything the
service writes down - the `request_log` collection, `app.log`, or the 422
handed back to the caller.

The values are the ones this repo really carries: `UserAccount.password` is
plain text and is hashed only after the request log has recorded the body,
and the staff master carries `pin` in plain text in requests and responses
alike.
"""

from kugel_common.utils.log_utils import mask_sensitive_data, mask_validation_error_details


class TestWhatIsMasked:
    def test_a_plaintext_password_does_not_survive(self):
        # POST /register takes UserAccount, whose password is plain text.
        body = {"username": "cashier01", "password": "hunter2", "isSuperuser": False}
        masked = mask_sensitive_data(body)
        assert masked == {"username": "cashier01", "password": "****", "isSuperuser": False}

    def test_a_staff_pin_does_not_survive_in_either_direction(self):
        # The staff master takes a pin on create and returns it on read, so
        # the response body is not the lesser half of this.
        assert mask_sensitive_data({"id": "S001", "name": "Ann", "pin": "1234"}) == {
            "id": "S001",
            "name": "Ann",
            "pin": "****",
        }

    def test_the_name_is_matched_across_spellings(self):
        # Bodies are lowerCamelCase (BaseSchemaModel sets to_lower_camel) while
        # the schemas and MongoDB documents are snake_case, so both reach a log
        # sink and both have to match.
        for key in ("pin_code", "pinCode", "PIN_CODE", "pin-code"):
            assert mask_sensitive_data({key: "1234"})[key] == "****", key

    def test_a_bearer_token_is_not_written_out(self):
        # The value of an Authorization header IS the credential.
        masked = mask_sensitive_data({"Authorization": "Bearer eyJhbGciOi.body.sig"})
        assert masked["Authorization"] == "****"

    def test_an_api_key_keeps_its_recognisable_ends(self):
        # Blanking it would break the troubleshooting workflow mask_dict_api_key
        # already established: first4...last4 identifies a key without being one.
        assert mask_sensitive_data({"api_key": "abcd1234efgh5678"}) == {"api_key": "abcd...5678"}

    def test_nested_and_repeated_values_are_reached(self):
        body = {"staff": {"id": "S001", "pin": "1234"}, "history": [{"pin": "9999"}]}
        masked = mask_sensitive_data(body)
        assert masked["staff"]["pin"] == "****"
        assert masked["history"][0]["pin"] == "****"
        assert masked["staff"]["id"] == "S001"


class TestWhatIsNotMasked:
    def test_ordinary_values_are_left_alone(self):
        # A log that masks everything records nothing worth reading.
        body = {"quantity": 3, "unitPrice": 120.0, "tokenType": "bearer", "note": None}
        assert mask_sensitive_data(body) == body

    def test_the_absence_of_a_secret_is_still_recorded(self):
        # None is preserved rather than blanked: "no PIN was supplied" and "a
        # PIN was supplied" are different requests, and telling them apart
        # reveals nothing.
        assert mask_sensitive_data({"pin": None}) == {"pin": None}

    def test_scalars_and_empty_values_pass_through(self):
        assert mask_sensitive_data(None) is None
        assert mask_sensitive_data("plain") == "plain"
        assert mask_sensitive_data(42) == 42
        assert mask_sensitive_data([]) == []

    def test_the_body_the_caller_is_still_using_is_not_modified(self):
        # This runs on the logging path of a request that is still being served.
        body = {"password": "hunter2", "staff": {"pin": "1234"}}
        mask_sensitive_data(body)
        assert body == {"password": "hunter2", "staff": {"pin": "1234"}}


class TestValuesTheMiddlewareCannotTrust:
    """The body is logged before FastAPI validates it, so it is any JSON at all."""

    def test_a_secret_field_carrying_the_wrong_type_is_still_masked(self):
        # A PIN sent as a number would slip past a str-only mask.
        assert mask_sensitive_data({"pin": 1234}) == {"pin": "****"}
        assert mask_sensitive_data({"pin": {"nested": "1234"}}) == {"pin": "****"}

    def test_a_non_string_api_key_does_not_raise(self):
        # mask_api_key measures len(), so a list under `apiKey` would be a
        # TypeError - raised on the logging path, which would turn the whole
        # request into a 500.
        for value in (1234, [1, 2], {"a": 1}, True):
            assert mask_sensitive_data({"apiKey": value}) == {"apiKey": "****"}

    def test_a_non_string_key_does_not_raise(self):
        # json.loads never produces one, but this is also used on dicts that
        # did not come from a request body.
        assert mask_sensitive_data({1: "x", None: "y"}) == {1: "x", None: "y"}


class TestACredentialContainer:
    """A field whose keys are not fixed cannot be covered by a name list."""

    def test_every_value_beneath_it_is_masked_whatever_the_key(self):
        body = {
            "provider": "prepaid",
            "credentials": {"cardN0": "8800001234563456", "pinCod": "654321", "note": None},
        }
        masked = mask_sensitive_data(body)
        assert masked["credentials"] == {"cardN0": "****", "pinCod": "****", "note": None}
        # The keys survive, so a misspelling is still diagnosable, and a field
        # outside the container is untouched.
        assert masked["provider"] == "prepaid"

    def test_nested_and_list_values_are_covered_too(self):
        masked = mask_sensitive_data({"credentials": {"extra": {"deep": "v"}, "arr": ["x", 7]}})
        assert masked["credentials"]["extra"] == {"deep": "****"}
        assert masked["credentials"]["arr"] == ["****", "****"]

    def test_the_singular_spelling_is_the_same_trap(self):
        assert mask_sensitive_data({"credential": {"cardN0": "8800001234563456"}}) == {"credential": {"cardN0": "****"}}


class TestTheValidationErrorEcho:
    """A 422 answers with the value it rejected, and logs it on the way out."""

    def test_the_input_at_a_secret_location_is_blanked(self):
        errors = [
            {"type": "string_type", "loc": ("body", "pin"), "msg": "…", "input": 9999, "ctx": {"x": 9999}},
            {"type": "string_type", "loc": ("body", "credentials", "cardN0"), "msg": "…", "input": 8800001234563456},
            {"type": "int_parsing", "loc": ("body", "quantity"), "msg": "…", "input": "abc"},
        ]
        masked = mask_validation_error_details(errors)

        assert masked[0]["input"] == "****"
        assert "ctx" not in masked[0], "ctx can carry the value back a second time"
        assert masked[1]["input"] == "****"
        assert masked[2]["input"] == "abc", "a non-secret location keeps its input, or the 422 is useless"
        assert "8800001234563456" not in str(masked)

    def test_a_root_level_error_carries_the_whole_body_and_is_still_masked(self):
        # A body sent as an array produces ONE error with loc=("body",) and the
        # entire body as its input. The location names nothing secret, so
        # location alone would let everything through.
        errors = [
            {
                "type": "model_attributes_type",
                "loc": ("body",),
                "msg": "Input should be a valid dictionary",
                "input": [{"username": "cashier01", "password": "hunter2"}],
            }
        ]
        masked = mask_validation_error_details(errors)

        assert "hunter2" not in str(masked)
        assert masked[0]["input"][0] == {"username": "cashier01", "password": "****"}

    def test_a_scalar_input_neither_crashes_nor_changes(self):
        masked = mask_validation_error_details(
            [{"type": "model_attributes_type", "loc": ("body",), "msg": "…", "input": "just-a-string"}]
        )
        assert masked[0]["input"] == "just-a-string"

    def test_a_missing_field_error_keeps_its_none(self):
        masked = mask_validation_error_details(
            [{"type": "missing", "loc": ("body", "password"), "msg": "Field required", "input": None}]
        )
        assert masked[0]["input"] is None

    def test_the_error_list_is_not_modified(self):
        errors = [{"type": "string_type", "loc": ("body", "pin"), "msg": "…", "input": 9999}]
        mask_validation_error_details(errors)
        assert errors[0]["input"] == 9999

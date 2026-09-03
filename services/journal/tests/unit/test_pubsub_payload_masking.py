# Copyright 2026 masa@kugel
"""What a received pub/sub message may be written down as (issue #211).

This service records the payloads it is handed. An `opencloselog` message is
a whole `OpenCloseLog`, which embeds a `TerminalInfoDocument` - api_key, and
the staff's pin one level down.

The producer redacts before publishing, so nothing leaks today. This is the
second layer: during a rolling deploy the producer may still be the old one,
and a consumer that depends on its producer's manners is one deploy away from
recording a credential.
"""

import inspect
import json

from app.api.v1 import tran
from kugel_common.utils.log_utils import mask_loggable, mask_sensitive_data


class _Log:
    """Stands in for the received model; only model_dump matters here."""

    def model_dump(self):
        return {
            "operation": "close",
            "terminal_info": {"terminal_id": "T-1", "api_key": "SECRET-KEY-VALUE", "staff": {"id": "S001", "pin": "1234"}},
        }


def test_the_envelope_is_masked_before_it_is_logged():
    # Only where `message` is the received envelope. The notifier further down
    # takes a `message: str` parameter of its own, which is the already-masked
    # error text - a blanket check on the name would have caught that too and
    # said nothing useful.
    source = inspect.getsource(tran)
    for site in ("new message: {message}", "{log_type}. message: {message}", "request: {req_json}"):
        assert site not in source, f"the raw pub/sub envelope is logged at: {site}"
    assert "mask_sensitive_data(message)" in source
    assert "mask_sensitive_data(req_json)" in source


def test_the_payload_is_masked_before_it_is_serialized():
    # The trap: `model_dump_json()` returns a STRING, and masking a string is
    # a no-op. The masking has to happen on the model.
    assert "log_data.model_dump_json()" not in inspect.getsource(tran), (
        "the payload is serialized before masking, so masking it does nothing"
    )
    assert "mask_loggable(log_data)" in inspect.getsource(tran)


def test_masking_a_serialized_payload_would_not_have_worked():
    # Spelled out because it is the kind of mistake that reads as correct.
    serialized = json.dumps(_Log().model_dump())
    assert "1234" in mask_sensitive_data(serialized), "precondition: masking a string does nothing"

    masked = json.dumps(mask_loggable(_Log()), default=str)
    assert "1234" not in masked
    assert "SECRET-KEY-VALUE" not in masked
    # The record stays readable.
    assert "T-1" in masked and "S001" in masked

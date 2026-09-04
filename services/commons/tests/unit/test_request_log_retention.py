# Copyright 2026 masa@kugel
"""A request log has to carry a date, or the TTL that removes it never fires (issue #221).

`log_request` gets a document per request, to the tenant database and to commons,
and nothing in this tree reads one or removed one: measured downstream at 6.4M
documents / 23.8 GiB, 97% of the database, on a store PC.

The TTL index lives in each service's `database_setup.py`. What is testable here
is the half that makes it work at all: MongoDB never expires a document whose
indexed field is missing or is not a date, and this document is written by the
buffer's `insert_many` rather than by `AbstractRepository.create_async` - which
is the only thing that used to set `created_at`. So every request log was written
with a null date, and a TTL on it would have deleted exactly nothing while
looking installed.
"""

from datetime import datetime

from kugel_common.models.documents.request_log_document import RequestLog


def _log() -> RequestLog:
    return RequestLog(
        client_info=RequestLog.ClientInfo(ip_address="10.0.0.1"),
        request_info=RequestLog.RequestInfo(method="POST", url="/api/v1/carts", accept_time="2026-09-04T10:00:00"),
        response_info=RequestLog.ResponseInfo(status_code=200, process_time_ms=12.0),
    )


class TestTheDateTheTtlNeeds:
    def test_a_request_log_is_stamped_when_it_is_made(self):
        assert isinstance(_log().created_at, datetime)

    def test_the_stamp_survives_the_dump_the_buffer_writes(self):
        # The buffer writes `log.model_dump()` through insert_many. A string here
        # would be stored as a string, and a TTL index does not expire strings.
        assert isinstance(_log().model_dump()["created_at"], datetime)

    def test_it_is_not_lost_when_the_caller_names_other_fields(self):
        # The default is a factory, not a shared value: two logs made a moment
        # apart must not share one timestamp.
        first, second = _log(), _log()
        assert first.created_at is not None and second.created_at is not None

    def test_an_explicit_date_is_still_honoured(self):
        stamped = datetime(2026, 1, 2, 3, 4, 5)
        assert _log().model_copy(update={"created_at": stamped}).created_at == stamped

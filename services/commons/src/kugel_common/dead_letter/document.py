# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
The dead-letter record, its states and the constants around it (#230).
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from pydantic import ValidationError

from kugel_common.config.settings import settings
from kugel_common.models.documents.abstract_document import AbstractDocument
from kugel_common.utils.log_utils import describe_exception_for_response

COLLECTION = "dead_letter"
ALERT_COLLECTION = "dead_letter_alert"
ALERT_WINDOW_ID = "alert-window"

STATE_FAILING = "failing"
STATE_PENDING = "pending"
STATE_REPLAYING = "replaying"
STATE_REPLAYED = "replayed"
STATE_DISCARDED = "discarded"
STATES = (STATE_FAILING, STATE_PENDING, STATE_REPLAYING, STATE_REPLAYED, STATE_DISCARDED)
LISTABLE_STATES = (STATE_PENDING, STATE_REPLAYING, STATE_REPLAYED, STATE_DISCARDED)

# Under these states another failure counts toward giving up; "none" is a new record
COUNTING_STATES = ("none", STATE_FAILING, STATE_REPLAYED, STATE_DISCARDED)
# Under these states the event is recorded already: a failure is acknowledged at once
RECORDED_STATES = (STATE_PENDING, STATE_REPLAYING)

TOPICS = ("topic-tranlog", "topic-cashlog", "topic-opencloselog")

FAILING_RETENTION = timedelta(days=1)
RESOLVED_RETENTION = timedelta(days=90)
REPLAY_LEASE = timedelta(minutes=10)
NOTIFY_LEASE = timedelta(minutes=10)
MAX_NOTIFY_ATTEMPTS = 5

RECORD_TIMEOUT_SECONDS = 5.0
SLACK_TIMEOUT_SECONDS = 5.0
REPLAY_TIMEOUT_SECONDS = 30.0

LAST_ERROR_MAX_LENGTH = 200
BULK_REPLAY_MAX = 100
SWEEP_BATCH = 100

SYSTEM_USER = "system"

SUMMARY_FIELDS = ("store_code", "terminal_no", "transaction_no", "business_date", "business_counter")


def give_up_after_failures() -> int:
    """The failure on which a subscriber stops asking for redelivery."""
    return settings.DEAD_LETTER_GIVE_UP_AFTER_FAILURES


class DeadLetterDocument(AbstractDocument):
    """
    One subscriber's record of one event it could not process.

    Stored with ``_id`` set to the event id: the database is per service and
    tenant, so the event id alone names the record, before any index exists.
    """

    event_id: str
    tenant_id: Optional[str] = None
    service: Optional[str] = None
    topic: Optional[str] = None
    state: str = STATE_FAILING
    message: Optional[dict] = None
    summary: dict = {}
    last_error: Optional[str] = None
    failure_count: int = 0
    episode_failure_count: int = 0
    dead_count: int = 0
    first_failed_at: Optional[datetime] = None
    last_failed_at: Optional[datetime] = None
    first_dead_at: Optional[datetime] = None
    last_dead_at: Optional[datetime] = None
    notified_at: Optional[datetime] = None
    notify_claimed_at: Optional[datetime] = None
    notify_attempts: int = 0
    replay_claim_id: Optional[str] = None
    replay_claimed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    purge_at: Optional[datetime] = None

    @classmethod
    def from_mongo(cls, raw: dict) -> "DeadLetterDocument":
        """Build from a stored document (``_id`` is the event id)."""
        values = {k: v for k, v in raw.items() if k != "_id"}
        values.setdefault("event_id", raw.get("_id"))
        return cls(**values)


def build_summary(data: Any) -> dict:
    """What a notification and a list show of an event: never its content."""
    if not isinstance(data, dict):
        return {}
    return {field: data[field] for field in SUMMARY_FIELDS if data.get(field) is not None}


def describe_failure(error: Any) -> str:
    """
    The reason a record keeps: an exception's type and its safe description.

    Uses the description meant for responses (#318), so a driver or validator
    error does not carry the values it was given, then cuts it short.
    """
    if isinstance(error, ValidationError):
        # Masking keeps any value whose key is not known to be sensitive; a
        # record and the API show only which fields failed
        fields = [".".join(str(part) for part in err.get("loc", ())) for err in error.errors()]
        text = f"{type(error).__name__}: fields {fields}"
    elif isinstance(error, BaseException):
        text = describe_exception_for_response(error)
    else:
        text = str(error) if error is not None else "unknown"
    if len(text) > LAST_ERROR_MAX_LENGTH:
        text = text[: LAST_ERROR_MAX_LENGTH - 3] + "..."
    return text


def failure_type(error: Any) -> str:
    """The reason a notification carries: the exception type only."""
    if isinstance(error, BaseException):
        return type(error).__name__
    text = str(error) if error is not None else "unknown"
    return text.split(":", 1)[0][:80]

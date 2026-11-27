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
What a subscriber's handler core reports (#230).

The core processes an event and says what happened, nothing else. It neither
records a failure nor tells the publisher: the subscription route does that, and
a replay reads the same outcome its own way. Kept apart so a failure during a
replay cannot turn into "already recorded, acknowledge" and then "replayed".
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OutcomeKind(str, Enum):
    PROCESSED = "processed"
    ALREADY_PROCESSED = "already_processed"
    DROPPED = "dropped"
    FAILED = "failed"


@dataclass(frozen=True)
class HandlerOutcome:
    """
    Attributes:
        kind: What happened
        reason: Why it was dropped or failed (no event content)
        error: The exception behind a failure, when there was one
    """

    kind: OutcomeKind
    reason: Optional[str] = None
    error: Optional[BaseException] = None

    @classmethod
    def processed(cls) -> "HandlerOutcome":
        return cls(OutcomeKind.PROCESSED)

    @classmethod
    def already_processed(cls) -> "HandlerOutcome":
        return cls(OutcomeKind.ALREADY_PROCESSED)

    @classmethod
    def dropped(cls, reason: str) -> "HandlerOutcome":
        return cls(OutcomeKind.DROPPED, reason=reason)

    @classmethod
    def failed(cls, error: BaseException | str) -> "HandlerOutcome":
        if isinstance(error, BaseException):
            return cls(OutcomeKind.FAILED, reason=type(error).__name__, error=error)
        return cls(OutcomeKind.FAILED, reason=str(error))

    @property
    def handled(self) -> bool:
        """True when the event is stored here (now or before)."""
        return self.kind in (OutcomeKind.PROCESSED, OutcomeKind.ALREADY_PROCESSED)

    @property
    def failure(self) -> BaseException | str:
        """What to describe a failure by."""
        return self.error if self.error is not None else (self.reason or "unknown")

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
Dead-letter settings, for the services that subscribe to pub/sub (#230)
"""

from pydantic_settings import BaseSettings


class DeadLetterSettings(BaseSettings):
    """
    Dead-letter settings

    Attributes:
        DEAD_LETTER_GIVE_UP_AFTER_FAILURES: A subscriber stops asking for
            redelivery on this failure of an event and records it as pending.
            It must stay at least two short of the sidecar's deliveries
            (resiliency maxRetries + 1): the subscriber cannot count a delivery
            that never reached it. 17 keeps about ten minutes of redelivery
        DEAD_LETTER_SWEEP_INTERVAL_SECONDS: How often the sweep runs
        DEAD_LETTER_STALE_FAILING_SECONDS: A failing record whose last failure
            is older than this is past every redelivery; the sweep resolves it
        DEAD_LETTER_NOTIFY_RETRY_AFTER_SECONDS: A pending record still not
            notified this long after it became pending is notified again
    """

    DEAD_LETTER_GIVE_UP_AFTER_FAILURES: int = 17
    DEAD_LETTER_SWEEP_INTERVAL_SECONDS: int = 300
    DEAD_LETTER_STALE_FAILING_SECONDS: int = 1800
    DEAD_LETTER_NOTIFY_RETRY_AFTER_SECONDS: int = 120

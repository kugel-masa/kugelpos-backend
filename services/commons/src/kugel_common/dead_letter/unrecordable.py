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
The notice for events that could not be recorded at all (R-5c).

A failure whose record cannot be written (the database is unreachable), or an
event without a tenant, has no record to carry a notification. It is announced
instead through a window kept in the service process: the first one in five
minutes is sent, the rest are counted and mentioned by the next window's first
notice. Per replica, and never raising.
"""

import time
from logging import getLogger
from typing import Optional

from kugel_common.dead_letter import alerts

logger = getLogger(__name__)

WINDOW_SECONDS = 300

_windows: dict[str, dict] = {}


def reset_windows() -> None:
    """For the tests."""
    _windows.clear()


def _count(service: str, now: float) -> tuple[bool, int]:
    """Whether to send now, and how many the previous window held back."""
    window = _windows.get(service)
    if window is None or now - window["started"] >= WINDOW_SECONDS:
        carried = window["suppressed"] if window else 0
        _windows[service] = {"started": now, "suppressed": 0}
        return True, carried
    window["suppressed"] += 1
    return False, 0


def format_unrecordable(
    service: str, topic: Optional[str], tenant_id: Optional[str], event_id: Optional[str], reason: str, carried: int
) -> str:
    lines = [
        f"[{service}] Events could not be recorded as dead letters: {topic or 'unknown'}",
        f"tenant: {tenant_id or 'unknown'}  event_id: {event_id or 'unknown'}",
        f"reason: {reason}",
        f"They are still being retried. If the retries run out they stay in dlq-{service}-{topic or '<topic>'}",
        "(check with: rabbitmqctl list_queues name messages).",
    ]
    if carried:
        lines.append(f"({carried} more in the previous 5 minutes)")
    return "\n".join(lines)


async def notify_unrecordable(
    *,
    service: str,
    topic: Optional[str],
    tenant_id: Optional[str],
    event_id: Optional[str],
    reason: str,
) -> None:
    """Announce an event that could not be recorded, at most once per window."""
    try:
        logger.error(
            f"Dead letter could not be recorded. service={service} topic={topic} tenant={tenant_id} "
            f"event_id={event_id} reason={reason}"
        )
        send_now, carried = _count(service, time.monotonic())
        if send_now:
            await alerts.send(format_unrecordable(service, topic, tenant_id, event_id, reason, carried), service)
    except Exception as e:  # noqa: BLE001 - this runs on failure paths
        logger.warning(f"Unrecordable notice failed ({type(e).__name__})")

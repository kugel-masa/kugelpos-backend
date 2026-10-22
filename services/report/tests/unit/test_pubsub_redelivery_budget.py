"""A report-family event that keeps failing ends in the dead-letter queue (issue #230).

report, journal and stock receive tranlog / cashlog / opencloselog through three
RabbitMQ components. When a delivery fails, the Dapr sidecar retries it
(dapr/components/pubsub-resiliency.yaml). When the retries run out, the
component has to hand the message to the dead-letter queue, which needs
`requeueInFailure: "false"` and `enableDeadLetter: "true"`. With requeueing on,
the message went straight back on the queue and was redelivered forever.

The retries also have to finish before RabbitMQ's consumer_timeout (30 minutes
by default). The sidecar holds the message unacknowledged while it retries; past
the timeout the broker requeues the message, and the retries start over.

Lives in report's unit tier because report subscribes to all three components.
The files are read as text: PyYAML is not a dependency here, and a shape the
patterns do not recognise fails loudly (nothing found) rather than passing.
"""

import re
from pathlib import Path

import pytest

DAPR_COMPONENTS = Path(__file__).resolve().parents[3] / "dapr" / "components"
REPORT_FAMILY_FILES = (
    "pubsub_tranlog_report.yaml",
    "pubsub_cashlog_report.yaml",
    "pubsub_opencloselog_report.yaml",
)

CONSUMER_TIMEOUT_SECONDS = 30 * 60

# Dapr's exponential back-off. Only maxInterval and maxRetries are configurable;
# the initial interval, the multiplier and the jitter are fixed.
INITIAL_INTERVAL_SECONDS = 0.5
MULTIPLIER = 1.5
RANDOMIZATION_FACTOR = 0.5

_COMPONENT_NAME = re.compile(r"^metadata:\s*\n\s+name:\s*(\S+)", re.MULTILINE)
_COMPONENT_TYPE = re.compile(r"^\s+type:\s*(\S+)", re.MULTILINE)
# A metadata item: its name, any comment lines, then its value.
_METADATA_ITEM = re.compile(
    r"-\s+name:\s*(\w+)\s*\n(?:\s*#.*\n)*\s+value:\s*\"?([^\"\n#]*?)\"?\s*(?:#.*)?$", re.MULTILINE
)


def _components() -> list[dict]:
    found = []
    for name in REPORT_FAMILY_FILES:
        text = (DAPR_COMPONENTS / name).read_text()
        found.append(
            {
                "name": _COMPONENT_NAME.search(text).group(1),
                "type": _COMPONENT_TYPE.search(text).group(1),
                "metadata": dict(_METADATA_ITEM.findall(text)),
            }
        )
    return found


def _resiliency() -> dict:
    """``{"targets": {component: policy}, "policies": {policy: {field: value}}}``."""
    text = (DAPR_COMPONENTS / "pubsub-resiliency.yaml").read_text()
    targets = dict(re.findall(r"^ {6}(\S+):\s*\n\s+inbound:\s*\n\s+retry:\s*(\S+)", text, re.MULTILINE))
    policies = {}
    for block in re.finditer(r"^ {6}(\w+):\s*\n((?: {8}\w+:.*\n)+)", text, re.MULTILINE):
        policies[block.group(1)] = dict(re.findall(r"^ {8}(\w+):\s*(\S+)", block.group(2), re.MULTILINE))
    return {"targets": targets, "policies": policies}


def _seconds(duration: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m|h)", duration.strip())
    assert match, f"cannot read the duration {duration!r}"
    value, unit = float(match.group(1)), match.group(2)
    return value * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]


def _longest_total_wait(policy: dict) -> float:
    """The total wait if every retry is jittered to its longest."""
    assert policy["policy"] == "exponential", policy
    cap = _seconds(policy["maxInterval"])
    retries = int(policy["maxRetries"])
    assert retries > 0, "an unbounded retry (-1) never reaches the dead-letter queue"
    total = 0.0
    interval = INITIAL_INTERVAL_SECONDS
    for _ in range(retries):
        total += min(interval, cap) * (1 + RANDOMIZATION_FACTOR)
        interval *= MULTIPLIER
    return total


@pytest.mark.parametrize("component", _components(), ids=lambda c: c["name"])
def test_a_failed_delivery_is_dead_lettered_not_put_back(component):
    assert component["type"] == "pubsub.rabbitmq"
    assert component["metadata"].get("requeueInFailure") == "false"
    assert component["metadata"].get("enableDeadLetter") == "true"


@pytest.mark.parametrize("component", _components(), ids=lambda c: c["name"])
def test_a_failed_delivery_is_retried_by_the_sidecar_first(component):
    resiliency = _resiliency()
    policy = resiliency["targets"].get(component["name"])
    assert policy, f"{component['name']} is not retried"
    assert policy in resiliency["policies"], f"{component['name']} names an unknown policy {policy!r}"


def test_the_retries_end_before_the_broker_times_the_consumer_out():
    resiliency = _resiliency()
    assert resiliency["targets"], "no retry targets read"
    for name, policy_name in resiliency["targets"].items():
        longest = _longest_total_wait(resiliency["policies"][policy_name])
        assert longest < CONSUMER_TIMEOUT_SECONDS, (
            f"{name}: the retries can take {longest / 60:.1f} minutes, "
            f"past the broker's {CONSUMER_TIMEOUT_SECONDS / 60:.0f}-minute consumer_timeout"
        )

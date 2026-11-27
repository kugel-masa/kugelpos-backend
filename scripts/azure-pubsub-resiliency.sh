#!/usr/bin/env bash
# Copyright 2026 masa@kugel
#
# Check, and with --apply set, the pub/sub redelivery budget of an Azure
# Container Apps environment (#230).
#
# Locally the sidecars read services/dapr/components/pubsub-resiliency.yaml.
# Container Apps ignores that file: the retries are a resiliency policy on each
# Dapr component of the environment. Without the same budget a subscriber
# cannot give up and record an event (it gives up on its 17th failure, the
# sidecar must deliver at least 19 times), and every failing event goes to
# dlq-* instead, where nobody sees it.
#
# The budget is read from pubsub-resiliency.yaml, so the two never drift:
# maxRetries and maxInterval from the file, and Dapr's exponential default of
# 500 ms for the first delay.
#
# Usage:
#   scripts/azure-pubsub-resiliency.sh -g <resource-group> -e <environment>           # check only
#   scripts/azure-pubsub-resiliency.sh -g <resource-group> -e <environment> --apply   # set what differs
#
# Options:
#   --give-up N   The subscribers' DEAD_LETTER_GIVE_UP_AFTER_FAILURES, if set (default 17)
#
# Exit status: 0 when everything matches (or was set), 1 when something does not,
# 2 on a usage or az error. The check changes nothing.
#
# It only reads the components' metadata: requeueInFailure must be "false" and
# enableDeadLetter "true" (#238). A mismatch there is reported, not changed,
# because the components carry the broker's connection secret.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESILIENCY_FILE="$PROJECT_ROOT/services/dapr/components/pubsub-resiliency.yaml"
COMPONENTS=(pubsub-tranlog-report pubsub-cashlog-report pubsub-opencloselog-report)
POLICY_NAME="pubsub-retry"
INITIAL_DELAY_MS=500

RESOURCE_GROUP=""
ENVIRONMENT=""
APPLY=false
GIVE_UP=17

usage() {
    sed -n '/^# Usage:/,/^# Exit status/p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        -g|--resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
        -e|--environment) ENVIRONMENT="$2"; shift 2 ;;
        --apply) APPLY=true; shift ;;
        --give-up) GIVE_UP="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done
[ -n "$RESOURCE_GROUP" ] && [ -n "$ENVIRONMENT" ] || usage
command -v az >/dev/null || { echo "az (Azure CLI) is not installed" >&2; exit 2; }

# -- the budget, from the repository's resiliency file ----------------------------

MAX_RETRIES="$(sed -n 's/^ *maxRetries: *\([0-9][0-9]*\) *$/\1/p' "$RESILIENCY_FILE" | head -1)"
MAX_INTERVAL="$(sed -n 's/^ *maxInterval: *\([0-9][0-9]*[smh]\) *$/\1/p' "$RESILIENCY_FILE" | head -1)"
[ -n "$MAX_RETRIES" ] && [ -n "$MAX_INTERVAL" ] || {
    echo "Could not read maxRetries / maxInterval from $RESILIENCY_FILE" >&2; exit 2;
}
case "$MAX_INTERVAL" in
    *s) MAX_INTERVAL_MS=$(( ${MAX_INTERVAL%s} * 1000 )) ;;
    *m) MAX_INTERVAL_MS=$(( ${MAX_INTERVAL%m} * 60000 )) ;;
    *h) MAX_INTERVAL_MS=$(( ${MAX_INTERVAL%h} * 3600000 )) ;;
esac

if [ "$MAX_RETRIES" -lt $(( GIVE_UP + 1 )) ]; then
    echo "pubsub-resiliency.yaml has maxRetries $MAX_RETRIES, too few for giving up after $GIVE_UP failures" \
         "(needs >= $(( GIVE_UP + 1 )))" >&2
    exit 2
fi

echo "Expected inbound retry policy: maxRetries $MAX_RETRIES, first delay ${INITIAL_DELAY_MS} ms," \
     "max interval ${MAX_INTERVAL_MS} ms (from pubsub-resiliency.yaml)"
echo "Environment: $ENVIRONMENT (resource group $RESOURCE_GROUP)$($APPLY && echo ', applying')"
echo

az_quiet() { az "$@" --only-show-errors 2>&1; }

FAILED=0
for component in "${COMPONENTS[@]}"; do
    echo "== $component"
    if ! az_quiet containerapp env dapr-component show -g "$RESOURCE_GROUP" -n "$ENVIRONMENT" \
            --dapr-component-name "$component" -o none >/dev/null; then
        echo "   NG  the component does not exist in this environment"
        FAILED=1
        continue
    fi

    for pair in requeueInFailure=false enableDeadLetter=true; do
        key="${pair%%=*}"; want="${pair#*=}"
        got="$(az_quiet containerapp env dapr-component show -g "$RESOURCE_GROUP" -n "$ENVIRONMENT" \
            --dapr-component-name "$component" \
            --query "properties.metadata[?name=='$key'].value | [0]" -o tsv)"
        if [ "$got" = "$want" ]; then
            echo "   ok  $key = $want"
        else
            echo "   NG  $key = ${got:-<not set>} (needs \"$want\"; change the component itself)"
            FAILED=1
        fi
    done

    policies="$(az_quiet containerapp env dapr-component resiliency list -g "$RESOURCE_GROUP" \
        --environment "$ENVIRONMENT" --dapr-component-name "$component" \
        --query "[].join(' ', [name, to_string(properties.inboundPolicy.httpRetryPolicy.maxRetries), to_string(properties.inboundPolicy.httpRetryPolicy.retryBackOff.initialDelayInMilliseconds), to_string(properties.inboundPolicy.httpRetryPolicy.retryBackOff.maxIntervalInMilliseconds)])" \
        -o tsv)" || { echo "   NG  could not list the resiliency policies: $policies"; FAILED=1; continue; }

    matching=""
    existing=""
    while read -r name retries delay interval; do
        [ -n "$name" ] || continue
        [ "$name" = "$POLICY_NAME" ] && existing="$name"
        echo "   ..  policy $name: maxRetries $retries, first delay $delay ms, max interval $interval ms"
        if [ "$retries" = "$MAX_RETRIES" ] && [ "$delay" = "$INITIAL_DELAY_MS" ] && [ "$interval" = "$MAX_INTERVAL_MS" ]; then
            matching="$name"
        fi
    done <<< "$policies"

    if [ -n "$matching" ]; then
        echo "   ok  inbound retries match (policy $matching)"
        continue
    fi
    if ! $APPLY; then
        echo "   NG  no policy has the expected inbound retries (run with --apply to set $POLICY_NAME)"
        FAILED=1
        continue
    fi
    verb=create
    [ -n "$existing" ] && verb=update
    if out="$(az_quiet containerapp env dapr-component resiliency "$verb" -g "$RESOURCE_GROUP" \
            --environment "$ENVIRONMENT" --dapr-component-name "$component" -n "$POLICY_NAME" \
            --in-http-retries "$MAX_RETRIES" --in-http-delay "$INITIAL_DELAY_MS" \
            --in-http-interval "$MAX_INTERVAL_MS" -o none)"; then
        echo "   set $POLICY_NAME ($verb)"
    else
        echo "   NG  could not $verb $POLICY_NAME: $out"
        FAILED=1
    fi
done

echo
if [ "$FAILED" -ne 0 ]; then
    echo "Something does not match: see the NG lines above."
    exit 1
fi
echo "All three components match."
echo "Note: Container Apps does not document the growth factor of its exponential back-off. If it is"
echo "larger than Dapr's 1.5, the 19 deliveries take longer than the 16 minutes measured locally."

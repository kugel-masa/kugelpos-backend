#!/usr/bin/env bash
# Copyright 2026 masa@kugel
#
# Check, and with --apply set, the Slack webhook of report, journal and stock on
# Azure Container Apps, from a Key Vault secret (#230).
#
# The dead-letter notices (and the services' other Slack notices) go to the
# incoming webhook in SLACK_WEBHOOK_URL. The URL is a secret and stays out of
# this repository: it lives in Key Vault, and each container app reads it
# through a Key Vault reference with a managed identity. To change the channel
# or rotate the URL, put a new version of the Key Vault secret; with a
# versionless secret URI the apps pick it up without running this again
# (Container Apps refreshes Key Vault references within about 30 minutes, and a
# new revision reads the latest at once).
#
# For each app it makes sure that:
#   1. the app has the managed identity (system-assigned, or the user-assigned one given)
#   2. the identity may read the vault's secrets
#      (role "Key Vault Secrets User" on an RBAC vault, "get" on secrets otherwise)
#   3. the app has the secret slack-webhook-url = keyvaultref:<secret URI>,identityref:<identity>
#   4. the app's container has SLACK_WEBHOOK_URL = secretref:slack-webhook-url
#
# Usage:
#   scripts/azure-slack-webhook.sh -g <resource-group> --secret-uri <uri> --apps "<report> <journal> <stock>"
#   ... --apply                         # set what differs
#   ... --identity <resource-id>        # a user-assigned identity instead of the system-assigned one
#
#   <uri> is the Key Vault secret's URI, preferably without a version:
#   https://<vault>.vault.azure.net/secrets/<name>
#   <report> <journal> <stock> are the container app names of the three services.
#
# Exit status: 0 when everything matches (or was set), 1 when something does not,
# 2 on a usage or az error. The check changes nothing.
#
# --apply needs rights to assign roles (or set access policies) on the vault and
# to update the apps. Each change to an app's secrets or environment makes a new
# revision. A role just assigned can take a few minutes to apply: if setting the
# secret fails right after it, run the script again.

set -euo pipefail

SECRET_NAME="slack-webhook-url"
ENV_NAME="SLACK_WEBHOOK_URL"
READER_ROLE="Key Vault Secrets User"

RESOURCE_GROUP=""
SECRET_URI=""
APPS=""
IDENTITY="system"
APPLY=false

usage() {
    sed -n '/^# Usage:/,/^# Exit status/p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        -g|--resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
        --secret-uri) SECRET_URI="$2"; shift 2 ;;
        --apps) APPS="$2"; shift 2 ;;
        --identity) IDENTITY="$2"; shift 2 ;;
        --apply) APPLY=true; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done
[ -n "$RESOURCE_GROUP" ] && [ -n "$SECRET_URI" ] && [ -n "$APPS" ] || usage
command -v az >/dev/null || { echo "az (Azure CLI) is not installed" >&2; exit 2; }

if [[ ! "$SECRET_URI" =~ ^https://([a-zA-Z0-9-]+)\.vault\.azure\.net/secrets/[a-zA-Z0-9-]+(/[a-zA-Z0-9]+)?/?$ ]]; then
    echo "--secret-uri must look like https://<vault>.vault.azure.net/secrets/<name>" >&2
    exit 2
fi
VAULT="${BASH_REMATCH[1]}"
[ -z "${BASH_REMATCH[2]}" ] || echo "Note: the secret URI names a version; rotating the URL then needs this script again."

az_q() { az "$@" --only-show-errors; }
FAILED=0
ng() { echo "   NG  $*"; FAILED=1; }

echo "Key Vault secret: $SECRET_URI"
echo "Identity: $IDENTITY$($APPLY && echo ', applying')"
echo

# -- the vault and the secret --------------------------------------------------

if ! vault_info="$(az_q keyvault show -n "$VAULT" --query "join(' ', [id, to_string(properties.enableRbacAuthorization)])" -o tsv 2>&1)"; then
    echo "Could not read the Key Vault $VAULT: $vault_info" >&2
    exit 2
fi
VAULT_ID="${vault_info% *}"
VAULT_RBAC="${vault_info##* }"
if enabled="$(az_q keyvault secret show --id "$SECRET_URI" --query attributes.enabled -o tsv 2>/dev/null)"; then
    [ "$enabled" = "true" ] && echo "ok  the secret exists and is enabled" || { echo "NG  the secret is disabled"; FAILED=1; }
else
    echo "..  could not read the secret itself (it may not exist, or you may lack 'get' on secrets): not checked"
fi
echo

# -- per app ------------------------------------------------------------------

identity_ref() { [ "$IDENTITY" = "system" ] && echo system || echo "$IDENTITY"; }

principal_of() {
    local app="$1"
    if [ "$IDENTITY" = "system" ]; then
        az_q containerapp identity show -n "$app" -g "$RESOURCE_GROUP" --query principalId -o tsv 2>/dev/null || true
    else
        az_q identity show --ids "$IDENTITY" --query principalId -o tsv 2>/dev/null || true
    fi
}

has_identity() {
    local app="$1"
    if [ "$IDENTITY" = "system" ]; then
        [ -n "$(principal_of "$app")" ]
    else
        az_q containerapp identity show -n "$app" -g "$RESOURCE_GROUP" --query "userAssignedIdentities" -o json 2>/dev/null \
            | grep -qi -- "\"$IDENTITY\""
    fi
}

can_read_secrets() {
    local principal="$1"
    if [ "$VAULT_RBAC" = "true" ]; then
        local n
        n="$(az_q role assignment list --assignee "$principal" --scope "$VAULT_ID" --include-inherited \
            --query "length([?roleDefinitionName=='$READER_ROLE' || roleDefinitionName=='Key Vault Secrets Officer' || roleDefinitionName=='Key Vault Administrator'])" \
            -o tsv 2>/dev/null || echo 0)"
        [ "${n:-0}" -gt 0 ]
    else
        az_q keyvault show -n "$VAULT" --query "properties.accessPolicies[?objectId=='$principal'].permissions.secrets[]" -o tsv 2>/dev/null \
            | grep -qiE '^(get|all)$'
    fi
}

grant_read() {
    local principal="$1"
    if [ "$VAULT_RBAC" = "true" ]; then
        az_q role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
            --role "$READER_ROLE" --scope "$VAULT_ID" -o none
    else
        az_q keyvault set-policy -n "$VAULT" --object-id "$principal" --secret-permissions get -o none
    fi
}

for app in $APPS; do
    echo "== $app"
    if ! az_q containerapp show -n "$app" -g "$RESOURCE_GROUP" -o none 2>/dev/null; then
        ng "the container app does not exist in $RESOURCE_GROUP"
        continue
    fi

    # 1. identity
    if has_identity "$app"; then
        echo "   ok  managed identity ($(identity_ref))"
    elif $APPLY; then
        if [ "$IDENTITY" = "system" ]; then
            az_q containerapp identity assign -n "$app" -g "$RESOURCE_GROUP" --system-assigned -o none \
                && echo "   set managed identity (system-assigned)" || { ng "could not assign the identity"; continue; }
        else
            az_q containerapp identity assign -n "$app" -g "$RESOURCE_GROUP" --user-assigned "$IDENTITY" -o none \
                && echo "   set managed identity (user-assigned)" || { ng "could not assign the identity"; continue; }
        fi
    else
        ng "the app does not have the managed identity ($(identity_ref))"
        continue
    fi

    # 2. read access to the vault
    principal="$(principal_of "$app")"
    if [ -z "$principal" ]; then
        ng "could not find the identity's principal id"
        continue
    fi
    if can_read_secrets "$principal"; then
        echo "   ok  the identity may read the vault's secrets"
    elif $APPLY; then
        grant_read "$principal" && echo "   set read access to the vault's secrets" \
            || { ng "could not grant read access (needs rights to assign roles or set access policies)"; continue; }
    else
        ng "the identity may not read the vault's secrets"
    fi

    # 3. the Key Vault reference
    want_ref="$(identity_ref)"
    current="$(az_q containerapp secret list -n "$app" -g "$RESOURCE_GROUP" \
        --query "[?name=='$SECRET_NAME'] | [0].join(' ', [to_string(keyVaultUrl), to_string(identity)])" -o tsv 2>/dev/null || true)"
    if [ "${current%% *}" = "$SECRET_URI" ] && [ "${current#* }" = "$want_ref" ]; then
        echo "   ok  secret $SECRET_NAME refers to the Key Vault secret"
    elif $APPLY; then
        az_q containerapp secret set -n "$app" -g "$RESOURCE_GROUP" \
            --secrets "$SECRET_NAME=keyvaultref:$SECRET_URI,identityref:$want_ref" -o none \
            && echo "   set secret $SECRET_NAME" \
            || { ng "could not set the secret (a role just assigned can take a few minutes: run again)"; continue; }
    else
        ng "secret $SECRET_NAME is ${current:-missing} (needs keyvaultref:$SECRET_URI,identityref:$want_ref)"
    fi

    # 4. the environment variable
    container="$(az_q containerapp show -n "$app" -g "$RESOURCE_GROUP" --query "properties.template.containers[0].name" -o tsv)"
    ref="$(az_q containerapp show -n "$app" -g "$RESOURCE_GROUP" \
        --query "properties.template.containers[0].env[?name=='$ENV_NAME'] | [0].secretRef" -o tsv 2>/dev/null || true)"
    if [ "$ref" = "$SECRET_NAME" ]; then
        echo "   ok  $ENV_NAME = secretref:$SECRET_NAME (container $container)"
    elif $APPLY; then
        az_q containerapp update -n "$app" -g "$RESOURCE_GROUP" --container-name "$container" \
            --set-env-vars "$ENV_NAME=secretref:$SECRET_NAME" -o none \
            && echo "   set $ENV_NAME = secretref:$SECRET_NAME (container $container, new revision)" \
            || ng "could not set $ENV_NAME"
    else
        ng "$ENV_NAME is ${ref:+secretref:}${ref:-not set from the secret} (container $container)"
    fi
done

echo
if [ "$FAILED" -ne 0 ]; then
    echo "Something does not match: see the NG lines above."
    exit 1
fi
echo "All apps read $ENV_NAME from the Key Vault secret."

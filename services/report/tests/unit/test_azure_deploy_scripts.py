# Copyright 2026 masa@kugel
"""The Azure deploy scripts for dead letters, run against a fake az (#230).

scripts/azure-pubsub-resiliency.sh and scripts/azure-slack-webhook.sh change an
Azure environment only with --apply. These tests put a fake `az` first on PATH
that answers from files in a state directory and records every call, and check
what each script reports, sets and leaves alone.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
RESILIENCY = ROOT / "scripts" / "azure-pubsub-resiliency.sh"
WEBHOOK = ROOT / "scripts" / "azure-slack-webhook.sh"
SECRET_URI = "https://kv1.vault.azure.net/secrets/slack-webhook-url"
APPS = "app-r app-j app-s"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

FAKE_AZ = r"""#!/usr/bin/env bash
# Answers from $FAKE_STATE; every call is appended to $FAKE_STATE/calls.
st="$FAKE_STATE"; a="$*"
echo "$a" >> "$st/calls"
app=""; [[ "$a" =~ -n\ ([a-z0-9-]+) ]] && app="${BASH_REMATCH[1]}"
comp=""; [[ "$a" =~ --dapr-component-name\ ([a-z0-9-]+) ]] && comp="${BASH_REMATCH[1]}"
case "$a" in
  # azure-pubsub-resiliency.sh
  "containerapp env dapr-component show"*"requeueInFailure"*) cat "$st/requeue" 2>/dev/null || echo false;;
  "containerapp env dapr-component show"*"enableDeadLetter"*) echo true;;
  "containerapp env dapr-component show"*) [ -f "$st/missing-$comp" ] && exit 1; exit 0;;
  "containerapp env dapr-component resiliency list"*) cat "$st/policy-$comp" 2>/dev/null; exit 0;;
  "containerapp env dapr-component resiliency create"*|"containerapp env dapr-component resiliency update"*)
    r=$(sed -n 's/.*--in-http-retries \([0-9]*\).*/\1/p' <<<"$a")
    d=$(sed -n 's/.*--in-http-delay \([0-9]*\).*/\1/p' <<<"$a")
    i=$(sed -n 's/.*--in-http-interval \([0-9]*\).*/\1/p' <<<"$a")
    echo "pubsub-retry $r $d $i" > "$st/policy-$comp";;
  # azure-slack-webhook.sh
  "keyvault show -n kv1 --query join"*) echo "/subs/x/vaults/kv1 $(cat "$st/rbac" 2>/dev/null || echo true)";;
  "keyvault secret show"*) echo true;;
  "containerapp show -n $app -g rg -o none"*) exit 0;;
  "containerapp identity show"*"principalId"*) [ -f "$st/id-$app" ] && echo "pid-$app"; exit 0;;
  "containerapp identity assign"*) touch "$st/id-$app";;
  "role assignment list"*) p=$(sed -n 's/.*--assignee \([^ ]*\).*/\1/p' <<<"$a"); [ -f "$st/role-$p" ] && echo 1 || echo 0;;
  "role assignment create"*) p=$(sed -n 's/.*--assignee-object-id \([^ ]*\).*/\1/p' <<<"$a"); touch "$st/role-$p";;
  "keyvault show -n kv1 --query properties.accessPolicies"*) [ -f "$st/policy-read" ] && echo get; exit 0;;
  "keyvault set-policy"*) touch "$st/policy-read";;
  "containerapp secret list"*) [ -f "$st/sec-$app" ] && echo "$(cat "$st/sec-$app")"; exit 0;;
  "containerapp secret set"*) echo "https://kv1.vault.azure.net/secrets/slack-webhook-url system" > "$st/sec-$app";;
  "containerapp show"*"containers[0].name"*) echo "$app";;
  "containerapp show"*"secretRef"*) [ -f "$st/env-$app" ] && echo slack-webhook-url; exit 0;;
  "containerapp update"*) touch "$st/env-$app";;
  *) echo "unexpected az call: $a" >&2; exit 3;;
esac
"""


@pytest.fixture
def fake_az(tmp_path):
    bin_dir = tmp_path / "bin"
    state = tmp_path / "state"
    bin_dir.mkdir()
    state.mkdir()
    az = bin_dir / "az"
    az.write_text(FAKE_AZ)
    az.chmod(0o755)

    def run(script: Path, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_STATE": str(state)}
        return subprocess.run(["bash", str(script), *args], capture_output=True, text=True, env=env, timeout=60)

    run.state = state
    return run


def _calls(fake_az, verb: str) -> int:
    calls = (fake_az.state / "calls").read_text().splitlines() if (fake_az.state / "calls").exists() else []
    return sum(verb in line for line in calls)


# -- azure-pubsub-resiliency.sh ------------------------------------------------------

RG_ENV = ("-g", "rg", "-e", "env")
COMPONENTS = ("pubsub-tranlog-report", "pubsub-cashlog-report", "pubsub-opencloselog-report")


def test_the_resiliency_check_reads_the_budget_from_the_repository_file(fake_az):
    result = fake_az(RESILIENCY, *RG_ENV)
    assert "maxRetries 18, first delay 500 ms, max interval 180000 ms (from pubsub-resiliency.yaml)" in result.stdout
    assert result.returncode == 1  # nothing set yet
    assert result.stdout.count("no policy has the expected inbound retries") == 3
    assert _calls(fake_az, "resiliency create") == 0 and _calls(fake_az, "resiliency update") == 0


def test_the_resiliency_apply_sets_each_component_and_the_check_then_passes(fake_az):
    (fake_az.state / "policy-pubsub-tranlog-report").write_text("pubsub-retry 3 1000 10000\n")
    applied = fake_az(RESILIENCY, *RG_ENV, "--apply")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert _calls(fake_az, "resiliency update") == 1  # the one that existed
    assert _calls(fake_az, "resiliency create") == 2
    for component in COMPONENTS:
        assert (fake_az.state / f"policy-{component}").read_text().split() == ["pubsub-retry", "18", "500", "180000"]
    checked = fake_az(RESILIENCY, *RG_ENV)
    assert checked.returncode == 0 and checked.stdout.count("inbound retries match") == 3


def test_the_resiliency_check_reports_a_requeueing_component_without_changing_it(fake_az):
    for component in COMPONENTS:
        (fake_az.state / f"policy-{component}").write_text("pubsub-retry 18 500 180000\n")
    (fake_az.state / "requeue").write_text("true\n")
    result = fake_az(RESILIENCY, *RG_ENV, "--apply")
    assert result.returncode == 1
    assert result.stdout.count('requeueInFailure = true (needs "false"; change the component itself)') == 3
    assert _calls(fake_az, "dapr-component set") == 0


def test_the_resiliency_check_refuses_a_give_up_the_budget_cannot_reach(fake_az):
    result = fake_az(RESILIENCY, *RG_ENV, "--give-up", "18")
    assert result.returncode == 2
    assert "needs >= 19" in result.stderr


# -- azure-slack-webhook.sh ----------------------------------------------------------

WEBHOOK_ARGS = ("-g", "rg", "--secret-uri", SECRET_URI, "--apps", APPS)


def test_the_webhook_check_changes_nothing(fake_az):
    result = fake_az(WEBHOOK, *WEBHOOK_ARGS)
    assert result.returncode == 1
    assert result.stdout.count("the app does not have the managed identity") == 3
    for verb in ("identity assign", "role assignment create", "secret set", "containerapp update"):
        assert _calls(fake_az, verb) == 0, verb


@pytest.mark.parametrize("rbac, grant", [("true", "role assignment create"), ("false", "keyvault set-policy")])
def test_the_webhook_apply_wires_each_app_to_key_vault(fake_az, rbac, grant):
    (fake_az.state / "rbac").write_text(rbac)
    applied = fake_az(WEBHOOK, *WEBHOOK_ARGS, "--apply")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert _calls(fake_az, "identity assign") == 3
    assert _calls(fake_az, grant) >= 1
    assert _calls(fake_az, "secret set") == 3
    assert _calls(fake_az, "set-env-vars SLACK_WEBHOOK_URL=secretref:slack-webhook-url") == 3
    assert f"slack-webhook-url=keyvaultref:{SECRET_URI},identityref:system" in (fake_az.state / "calls").read_text()
    checked = fake_az(WEBHOOK, *WEBHOOK_ARGS)
    assert checked.returncode == 0, checked.stdout
    assert "All apps read SLACK_WEBHOOK_URL from the Key Vault secret." in checked.stdout


def test_the_webhook_script_refuses_a_uri_that_is_not_a_key_vault_secret(fake_az):
    result = fake_az(WEBHOOK, "-g", "rg", "--secret-uri", "https://example.com/x", "--apps", APPS)
    assert result.returncode == 2
    assert "must look like https://<vault>.vault.azure.net/secrets/<name>" in result.stderr
    assert not (fake_az.state / "calls").exists()

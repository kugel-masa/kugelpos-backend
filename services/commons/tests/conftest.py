# Copyright 2026 masa@kugel
"""Shared by every tier of the kugel_common tests."""

import os

import pytest

# Tests never post to Slack (#230). The webhook stays out of the tests' .env
# files, but one exported in the shell, or read from services/.env when pytest
# runs there, would still reach slack_notifier, which reads it once at import.
# Blanked here for the settings, and per test on the module itself, so even a
# test that builds its own settings sends nothing; a test that wants a webhook
# patches slack_notifier.SLACK_WEBHOOK_URL itself, after this fixture.
os.environ["SLACK_WEBHOOK_URL"] = ""

@pytest.fixture(autouse=True)
def _no_real_slack(monkeypatch):
    try:
        from kugel_common.utils import slack_notifier
    except ImportError:  # a service without aiohttp cannot post to Slack at all
        return
    monkeypatch.setattr(slack_notifier, "SLACK_WEBHOOK_URL", "")


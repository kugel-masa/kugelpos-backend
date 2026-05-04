# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.utils.slack_notifier.

The actual aiohttp call is patched out — we only verify the helper's
input handling, payload shaping, and short-circuit when SLACK_WEBHOOK_URL
is not configured.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kugel_common.utils import slack_notifier
from kugel_common.utils.slack_notifier import (
    send_error_notification,
    send_fatal_error_notification,
    send_info_notification,
    send_slack_notification,
    send_warning_notification,
)


def _make_mock_session(status: int = 200, response_text: str = ""):
    """Build a mock aiohttp.ClientSession that returns a fixed response."""
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=response_text)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    post = MagicMock(return_value=response)

    session = MagicMock()
    session.post = post
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    return session, post


class TestSendSlackNotification:
    @pytest.mark.asyncio
    async def test_skipped_when_webhook_url_missing(self):
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", None):
            result = await send_slack_notification("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_successful_post_returns_true(self):
        session, _ = _make_mock_session(status=200)
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
            with patch("aiohttp.ClientSession", return_value=session):
                result = await send_slack_notification("hello")
        assert result is True

    @pytest.mark.asyncio
    async def test_non_200_returns_false(self):
        session, _ = _make_mock_session(status=500, response_text="oops")
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
            with patch("aiohttp.ClientSession", return_value=session):
                result = await send_slack_notification("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_payload_shape(self):
        session, post = _make_mock_session(status=200)
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
            with patch("aiohttp.ClientSession", return_value=session):
                await send_slack_notification(
                    message="something bad",
                    title="My Title",
                    level="error",
                    error_details="trace info",
                    additional_fields={"Tenant": "T001"},
                    service="cart",
                )

        # Inspect the call args to .post
        post.assert_called_once()
        kwargs = post.call_args.kwargs
        assert kwargs["headers"] == {"Content-Type": "application/json"}
        body = json.loads(kwargs["data"])
        attachment = body["attachments"][0]
        assert attachment["title"] == "My Title"
        assert attachment["text"] == "something bad"
        assert attachment["color"] == "#ff0000"
        # fields contains Time / Level / Service / Details / Tenant
        titles = {f["title"] for f in attachment["fields"]}
        assert {"Time", "Level", "Service", "Details", "Tenant"}.issubset(titles)

    @pytest.mark.asyncio
    async def test_long_error_details_truncated(self):
        session, post = _make_mock_session(status=200)
        long_detail = "x" * 2000
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
            with patch("aiohttp.ClientSession", return_value=session):
                await send_slack_notification("m", error_details=long_detail)
        body = json.loads(post.call_args.kwargs["data"])
        details_field = next(f for f in body["attachments"][0]["fields"] if f["title"] == "Details")
        assert details_field["value"].endswith("...")
        assert len(details_field["value"]) <= 1003  # 1000 chars + "..."

    @pytest.mark.asyncio
    async def test_color_per_level(self):
        session, post = _make_mock_session(status=200)
        levels_to_colors = {
            "error": "#ff0000",
            "fatal": "#9b0000",
            "warning": "#ffcc00",
            "info": "#0099ff",
            "weird": "#717171",  # default
        }
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
            with patch("aiohttp.ClientSession", return_value=session):
                for level, expected_color in levels_to_colors.items():
                    post.reset_mock()
                    await send_slack_notification("m", level=level)
                    body = json.loads(post.call_args.kwargs["data"])
                    assert body["attachments"][0]["color"] == expected_color

    @pytest.mark.asyncio
    async def test_aiohttp_exception_returns_false(self):
        with patch.object(slack_notifier, "SLACK_WEBHOOK_URL", "http://hooks/x"):
            with patch("aiohttp.ClientSession", side_effect=RuntimeError("connection")):
                result = await send_slack_notification("hello")
        assert result is False


class TestConvenienceWrappers:
    """The four convenience wrappers should all delegate to send_slack_notification."""

    @pytest.mark.asyncio
    async def test_fatal_uses_fatal_level(self):
        with patch(
            "kugel_common.utils.slack_notifier.send_slack_notification",
            new_callable=AsyncMock,
            return_value=True,
        ) as send:
            await send_fatal_error_notification("boom", error=ValueError("x"))
        send.assert_awaited_once()
        kwargs = send.await_args.kwargs
        assert kwargs["level"] == "fatal"
        assert kwargs["title"].startswith("❌")

    @pytest.mark.asyncio
    async def test_error_uses_error_level(self):
        with patch(
            "kugel_common.utils.slack_notifier.send_slack_notification",
            new_callable=AsyncMock,
            return_value=True,
        ) as send:
            await send_error_notification("bad")
        kwargs = send.await_args.kwargs
        assert kwargs["level"] == "error"

    @pytest.mark.asyncio
    async def test_warning_uses_warning_level(self):
        with patch(
            "kugel_common.utils.slack_notifier.send_slack_notification",
            new_callable=AsyncMock,
            return_value=True,
        ) as send:
            await send_warning_notification("careful")
        kwargs = send.await_args.kwargs
        assert kwargs["level"] == "warning"

    @pytest.mark.asyncio
    async def test_info_uses_info_level(self):
        with patch(
            "kugel_common.utils.slack_notifier.send_slack_notification",
            new_callable=AsyncMock,
            return_value=True,
        ) as send:
            await send_info_notification("fyi")
        kwargs = send.await_args.kwargs
        assert kwargs["level"] == "info"

    @pytest.mark.asyncio
    async def test_context_propagated_to_additional_fields(self):
        with patch(
            "kugel_common.utils.slack_notifier.send_slack_notification",
            new_callable=AsyncMock,
            return_value=True,
        ) as send:
            await send_error_notification(
                "msg",
                context={"tenant_id": "T001", "request_id": "r-42"},
            )
        kwargs = send.await_args.kwargs
        af = kwargs["additional_fields"]
        assert af["tenant_id"] == "T001"
        assert af["request_id"] == "r-42"

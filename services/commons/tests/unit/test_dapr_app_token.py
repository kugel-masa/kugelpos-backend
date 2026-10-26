# Copyright 2026 masa@kugel
"""Only what a service's own Dapr sidecar delivers reaches its pub/sub routes (issue #134).

The pub/sub routes of report, journal and stock carry no JWT and pick the
tenant database from the event body, so anyone who could reach the app port
could write into any tenant. A daprd sidecar started with APP_API_TOKEN sends
it as the dapr-api-token header on every delivery; the routes now require it,
and the service refuses to start without a token of its own.
"""

import logging

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from kugel_common.config.settings_auth import AuthSettings
from kugel_common.config.settings_dapr_app_token import PUBLISHED_APP_API_TOKENS, DaprAppTokenSettings
from kugel_common.utils.dapr_app_token import DAPR_APP_TOKEN_HEADER, make_dapr_app_token_verifier

OWN_TOKEN = "an-app-token-of-this-deployment-only-0123456789"
DEV_TOKEN = next(iter(PUBLISHED_APP_API_TOKENS))


@pytest.fixture(autouse=True)
def _production_like(monkeypatch):
    # The test conftest allows the published values for every other test.
    for name in ("ALLOW_INSECURE_DEV_SECRETS", "APP_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)


class SubscriberSettings(AuthSettings, DaprAppTokenSettings):
    # How report, journal and stock compose it, with keys of their own.
    model_config = SettingsConfigDict(env_file=None, env_ignore_empty=True)


def _settings(**values) -> SubscriberSettings:
    return SubscriberSettings(
        SECRET_KEY="a-secret-of-this-deployment-only-0123456789",
        PUBSUB_NOTIFY_API_KEY="an-api-key-of-this-deployment-only-0123456789",
        **values,
    )


class TestTheServiceRefusesToStart:
    def test_without_a_token(self):
        with pytest.raises(ValidationError) as raised:
            _settings()

        assert "APP_API_TOKEN is not set" in str(raised.value)

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_on_an_empty_token(self, monkeypatch, value):
        # env_ignore_empty turns an empty APP_API_TOKEN= into the default, which is empty too.
        monkeypatch.setenv("APP_API_TOKEN", value)

        with pytest.raises(ValidationError):
            _settings()

    @pytest.mark.parametrize("value", [DEV_TOKEN, f" {DEV_TOKEN} "])
    def test_on_the_published_token(self, value):
        with pytest.raises(ValidationError) as raised:
            _settings(APP_API_TOKEN=value)

        assert "published in the repository" in str(raised.value)

    def test_on_an_empty_token_even_with_the_development_flag(self, monkeypatch):
        # The flag accepts the published token, never none: none would turn the check off.
        monkeypatch.setenv("ALLOW_INSECURE_DEV_SECRETS", "true")

        with pytest.raises(ValidationError):
            _settings()

    def test_without_repeating_the_token_it_was_given(self):
        with pytest.raises(ValidationError) as raised:
            _settings(APP_API_TOKEN=DEV_TOKEN)

        assert "input_value" not in str(raised.value)


class TestTheServiceStarts:
    def test_on_a_token_of_its_own(self):
        assert _settings(APP_API_TOKEN=OWN_TOKEN).APP_API_TOKEN == OWN_TOKEN

    def test_on_the_published_token_with_the_development_flag_and_a_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("ALLOW_INSECURE_DEV_SECRETS", "true")

        with caplog.at_level(logging.WARNING, logger="kugel_common.config.settings_dapr_app_token"):
            settings = _settings(APP_API_TOKEN=DEV_TOKEN)

        assert settings.APP_API_TOKEN == DEV_TOKEN
        assert any("APP_API_TOKEN" in record.message for record in caplog.records)


def _app(expected: str) -> FastAPI:
    app = FastAPI()
    verify = make_dapr_app_token_verifier(lambda: expected)
    reached = []

    @app.post("/api/v1/tranlog", dependencies=[Depends(verify)])
    async def tranlog():
        reached.append(True)
        return {"status": "SUCCESS"}

    app.state.reached = reached
    return app


async def _deliver(app: FastAPI, headers: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/v1/tranlog", json={"data": {"tenant_id": "T001"}}, headers=headers)


class TestTheRoute:
    @pytest.mark.asyncio
    async def test_takes_a_delivery_carrying_the_token(self):
        app = _app(OWN_TOKEN)

        response = await _deliver(app, {DAPR_APP_TOKEN_HEADER: OWN_TOKEN})

        assert response.status_code == 200
        assert app.state.reached == [True]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {DAPR_APP_TOKEN_HEADER: ""},
            {DAPR_APP_TOKEN_HEADER: "a-token-someone-guessed"},
            {DAPR_APP_TOKEN_HEADER: OWN_TOKEN[:-1]},
            {DAPR_APP_TOKEN_HEADER: OWN_TOKEN + "x"},
            # A JWT or an API key is not the sidecar's token.
            {"Authorization": f"Bearer {OWN_TOKEN}"},
            {"X-API-KEY": OWN_TOKEN},
        ],
    )
    async def test_refuses_anything_else_before_the_handler_runs(self, headers):
        app = _app(OWN_TOKEN)

        response = await _deliver(app, headers)

        assert response.status_code == 401
        assert app.state.reached == []
        assert OWN_TOKEN not in response.text

    @pytest.mark.asyncio
    async def test_refuses_everything_when_no_token_is_configured(self):
        # The settings refuse to start without one; if they are bypassed, nothing gets through.
        app = _app("")

        response = await _deliver(app, {DAPR_APP_TOKEN_HEADER: ""})

        assert response.status_code == 401
        assert app.state.reached == []

    @pytest.mark.asyncio
    async def test_reads_the_token_on_each_request(self):
        current = {"token": OWN_TOKEN}
        app = FastAPI()
        verify = make_dapr_app_token_verifier(lambda: current["token"])

        @app.post("/api/v1/tranlog", dependencies=[Depends(verify)])
        async def tranlog():
            return {"status": "SUCCESS"}

        current["token"] = "rotated-" + OWN_TOKEN

        assert (await _deliver(app, {DAPR_APP_TOKEN_HEADER: OWN_TOKEN})).status_code == 401
        assert (await _deliver(app, {DAPR_APP_TOKEN_HEADER: current["token"]})).status_code == 200

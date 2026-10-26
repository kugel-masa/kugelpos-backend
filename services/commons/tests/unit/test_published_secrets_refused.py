# Copyright 2026 masa@kugel
"""A service refuses to start on a SECRET_KEY / PUBSUB_NOTIFY_API_KEY anyone can read (issue #132).

Both fell back to values committed to the repository, and nothing checked
them. SECRET_KEY signs every JWT (HS256), so with the published value anyone
could forge a superuser token for any tenant; PUBSUB_NOTIFY_API_KEY is
accepted in place of any terminal's API key.
"""

import logging

import pytest
from pydantic import Field, ValidationError
from pydantic_settings import SettingsConfigDict

from kugel_common.config.settings import Settings
from kugel_common.config.settings_auth import PUBLISHED_SECRET_VALUES, AuthSettings

OWN_SECRET = "a-secret-of-this-deployment-only-0123456789"
OWN_API_KEY = "an-api-key-of-this-deployment-only-0123456789"


@pytest.fixture(autouse=True)
def _production_like(monkeypatch):
    # The test conftest allows the published keys for every other test.
    for name in ("ALLOW_INSECURE_DEV_SECRETS", "SECRET_KEY", "PUBSUB_NOTIFY_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def _settings(**env) -> Settings:
    # No .env file: only what the test sets reaches the settings.
    return Settings(_env_file=None, **env)


def test_the_published_defaults_are_refused():
    with pytest.raises(ValidationError) as raised:
        _settings()

    assert "SECRET_KEY and PUBSUB_NOTIFY_API_KEY" in str(raised.value)


@pytest.mark.parametrize("value", sorted(PUBLISHED_SECRET_VALUES))
@pytest.mark.parametrize("name", ["SECRET_KEY", "PUBSUB_NOTIFY_API_KEY"])
def test_a_published_value_is_refused(name, value):
    own = {"SECRET_KEY": OWN_SECRET, "PUBSUB_NOTIFY_API_KEY": OWN_API_KEY}
    own[name] = value

    with pytest.raises(ValidationError) as raised:
        _settings(**own)

    assert name in str(raised.value)


@pytest.mark.parametrize("name", ["SECRET_KEY", "PUBSUB_NOTIFY_API_KEY"])
def test_an_empty_value_in_the_environment_is_refused(monkeypatch, name):
    # env_ignore_empty drops it and the published default takes its place.
    monkeypatch.setenv("SECRET_KEY", OWN_SECRET)
    monkeypatch.setenv("PUBSUB_NOTIFY_API_KEY", OWN_API_KEY)
    monkeypatch.setenv(name, "")

    with pytest.raises(ValidationError):
        _settings()


@pytest.mark.parametrize("padded", ["your_secret_key ", " test-secret-key-for-development-only", "\tdev-api-key-123456789\n"])
@pytest.mark.parametrize("name", ["SECRET_KEY", "PUBSUB_NOTIFY_API_KEY"])
def test_a_published_value_with_spaces_around_it_is_refused(monkeypatch, name, padded):
    # account's .env.sample published "your_secret_key " with the space, and
    # an environment variable keeps it.
    monkeypatch.setenv("SECRET_KEY", OWN_SECRET)
    monkeypatch.setenv("PUBSUB_NOTIFY_API_KEY", OWN_API_KEY)
    monkeypatch.setenv(name, padded)

    with pytest.raises(ValidationError) as raised:
        _settings()

    assert name in str(raised.value)


def test_a_blank_value_is_refused():
    with pytest.raises(ValidationError):
        _settings(SECRET_KEY="   ", PUBSUB_NOTIFY_API_KEY=OWN_API_KEY)


def test_secrets_of_the_deployment_are_accepted(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", OWN_SECRET)
    monkeypatch.setenv("PUBSUB_NOTIFY_API_KEY", OWN_API_KEY)

    settings = _settings()

    assert settings.SECRET_KEY == OWN_SECRET
    assert settings.PUBSUB_NOTIFY_API_KEY == OWN_API_KEY


def test_the_development_flag_lets_the_published_defaults_start_with_a_warning(monkeypatch, caplog):
    monkeypatch.setenv("ALLOW_INSECURE_DEV_SECRETS", "true")

    with caplog.at_level(logging.WARNING, logger="kugel_common.config.settings_auth"):
        settings = _settings()

    assert settings.SECRET_KEY == "test-secret-key-for-development-only"
    assert any("ALLOW_INSECURE_DEV_SECRETS" in record.message for record in caplog.records)


def test_a_service_that_redeclares_a_key_is_still_checked():
    # stock declares its own PUBSUB_NOTIFY_API_KEY, defaulting to empty.
    class ServiceSettings(AuthSettings):
        PUBSUB_NOTIFY_API_KEY: str = Field(default="")
        model_config = SettingsConfigDict(env_file=None)

    with pytest.raises(ValidationError) as raised:
        ServiceSettings(SECRET_KEY=OWN_SECRET)

    assert "PUBSUB_NOTIFY_API_KEY" in str(raised.value)


def test_the_refusal_does_not_repeat_the_values_it_was_given():
    with pytest.raises(ValidationError) as raised:
        _settings(SECRET_KEY=OWN_SECRET, PUBSUB_NOTIFY_API_KEY="")

    # pydantic shortens a long input, so the whole value may be cut out of it
    # anyway; what must not be there is the input at all.
    assert "input_value" not in str(raised.value)
    assert OWN_SECRET[:12] not in str(raised.value)


def test_a_service_settings_class_keeps_the_values_out_of_its_errors():
    # Each service declares a model_config of its own; pydantic merges it with this one.
    class ServiceSettings(AuthSettings):
        model_config = SettingsConfigDict(env_file=None, env_ignore_empty=True)

    with pytest.raises(ValidationError) as raised:
        ServiceSettings(SECRET_KEY=OWN_SECRET)

    # pydantic shortens a long input, so the whole value may be cut out of it
    # anyway; what must not be there is the input at all.
    assert "input_value" not in str(raised.value)
    assert OWN_SECRET[:12] not in str(raised.value)

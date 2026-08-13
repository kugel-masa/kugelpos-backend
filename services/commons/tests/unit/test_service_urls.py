# Copyright 2026 masa@kugel
"""Unit tests for kugel_common.config.service_urls."""
import logging

import pytest

from kugel_common.config.service_urls import (
    RequiredServiceUrlsMissingError,
    verify_service_urls,
)


class _FakeSettings:
    """Stands in for a pydantic-settings instance, exposing model_fields_set."""

    def __init__(self, configured):
        self.model_fields_set = set(configured)


class TestVerifyServiceUrls:
    def test_passes_when_every_required_setting_is_configured(self):
        settings = _FakeSettings({"BASE_URL_TERMINAL", "BASE_URL_MASTER_DATA"})
        # Must not raise.
        verify_service_urls(
            "cart",
            required=["BASE_URL_TERMINAL", "BASE_URL_MASTER_DATA"],
            settings_obj=settings,
        )

    def test_raises_and_names_every_missing_setting(self):
        settings = _FakeSettings({"BASE_URL_TERMINAL"})
        with pytest.raises(RequiredServiceUrlsMissingError) as excinfo:
            verify_service_urls(
                "report",
                required=["BASE_URL_TERMINAL", "BASE_URL_MASTER_DATA", "BASE_URL_JOURNAL"],
                settings_obj=settings,
            )
        err = excinfo.value
        assert err.service_name == "report"
        # Both missing names are reported at once, so one restart surfaces the
        # whole gap rather than one name per attempt.
        assert err.missing == ["BASE_URL_MASTER_DATA", "BASE_URL_JOURNAL"]
        assert "BASE_URL_MASTER_DATA" in str(err)
        assert "BASE_URL_JOURNAL" in str(err)

    def test_a_value_equal_to_the_default_still_counts_as_configured(self):
        # The check is "was it explicitly provided", not "does it differ from the
        # default". A deployment may legitimately set the same value as the
        # default, and that must not be reported as missing.
        settings = _FakeSettings({"BASE_URL_TERMINAL"})
        verify_service_urls(
            "master-data", required=["BASE_URL_TERMINAL"], settings_obj=settings
        )

    def test_advisory_settings_warn_but_do_not_raise(self, caplog):
        settings = _FakeSettings({"BASE_URL_TERMINAL"})
        with caplog.at_level(logging.WARNING, logger="kugel_common.config.service_urls"):
            verify_service_urls(
                "journal",
                required=["BASE_URL_TERMINAL"],
                advisory=["TOKEN_URL"],
                settings_obj=settings,
            )
        assert "TOKEN_URL" in caplog.text

    def test_empty_required_set_is_allowed(self):
        # account calls no other service.
        verify_service_urls("account", required=[], settings_obj=_FakeSettings(set()))

    def test_defaults_to_the_shared_settings_singleton(self):
        # _get_service_url reads the same object, so the check must inspect it too
        # rather than a separately constructed Settings instance.
        from kugel_common.config.settings import settings as shared

        verify_service_urls("cart", required=[])
        assert hasattr(shared, "model_fields_set")

# Copyright 2026 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Signing is a startup requirement, not a feature that degrades (issue #192).

A cart on the carried path is held by the client alone: the server writes
nothing. So a response without a signed snapshot does not merely lose a feature,
it loses the cart — the client has a cart_id addressing nothing and no envelope
to present. Before this, a cart service with no key started anyway, answered
`signedSnapshot: null`, and every carried cart it created died on the next
request with a 404.

Two halves, and both are needed. Startup removes the configuration cases, so no
request is ever served by a process that cannot sign. The response check covers
what is left: a key that loads and then fails to sign.
"""

import base64

import pytest

from app.config.settings import settings
from app.services import snapshot_service
from app.services.snapshot_service import (
    PUBLICLY_KNOWN_KEY_MATERIAL,
    SnapshotSigningUnavailableError,
    require_snapshot_signer,
)

REAL_KEY = "v1:" + base64.b64encode(b"a-key-that-is-not-in-the-repo!!!").decode()
PUBLIC_KEY = "dev-v1:" + PUBLICLY_KNOWN_KEY_MATERIAL[0]


@pytest.fixture(autouse=True)
def _restore_signer():
    """Leave the module's key ring as it was; it is global state."""
    yield
    snapshot_service.init_snapshot_signer(force=True)


def _configure(monkeypatch, spec, allow_insecure=False):
    monkeypatch.setattr(settings, "SNAPSHOT_HMAC_KEYS", spec)
    monkeypatch.setattr(settings, "SNAPSHOT_ALLOW_INSECURE_KEY", allow_insecure)


class TestStartupRefusesToRunUnsigned:
    def test_no_key_stops_the_service(self, monkeypatch):
        _configure(monkeypatch, "")

        with pytest.raises(SnapshotSigningUnavailableError):
            require_snapshot_signer()

    def test_a_malformed_key_stops_the_service(self, monkeypatch):
        # Loading this raises inside HmacSigner, which init reports and swallows.
        # Swallowing it was the whole degraded mode; it must not survive startup.
        _configure(monkeypatch, "v1:not-base64-at-all")

        with pytest.raises(SnapshotSigningUnavailableError):
            require_snapshot_signer()

    def test_a_key_that_is_too_short_stops_the_service(self, monkeypatch):
        _configure(monkeypatch, "v1:" + base64.b64encode(b"short").decode())

        with pytest.raises(SnapshotSigningUnavailableError):
            require_snapshot_signer()

    def test_a_real_key_starts(self, monkeypatch):
        _configure(monkeypatch, REAL_KEY)

        signer = require_snapshot_signer()

        assert signer is not None
        assert signer.current_kid == "v1"


class TestTheKeyPublishedInThisRepository:
    """It signs and verifies, so nothing else would ever surface it.

    A deployment that inherits it looks healthy in every log and every response
    while anyone who can read the repository can mint a snapshot with any prices
    in it. An ERROR log was the previous answer and is not one: it scrolls past.
    """

    def test_it_stops_the_service_by_default(self, monkeypatch):
        _configure(monkeypatch, PUBLIC_KEY)

        with pytest.raises(SnapshotSigningUnavailableError):
            require_snapshot_signer()

    def test_a_development_stack_says_so_and_starts(self, monkeypatch):
        _configure(monkeypatch, PUBLIC_KEY, allow_insecure=True)

        assert require_snapshot_signer() is not None

    def test_it_is_caught_alongside_a_real_key(self, monkeypatch):
        # Appending a good key does not launder the published one: the first
        # entry signs, and either position leaves the material public.
        _configure(monkeypatch, f"{PUBLIC_KEY},{REAL_KEY}")

        with pytest.raises(SnapshotSigningUnavailableError):
            require_snapshot_signer()

    def test_the_opt_in_does_not_excuse_a_missing_key(self, monkeypatch):
        _configure(monkeypatch, "", allow_insecure=True)

        with pytest.raises(SnapshotSigningUnavailableError):
            require_snapshot_signer()


class TestACarriedCartIsNeverReturnedUnsigned:
    """The other half: a key that loads and then fails to sign.

    Startup cannot see this one — the ring is valid — so the response path has to.
    A cart the server keeps is unaffected: its snapshot is a convenience and the
    field goes out null, exactly as before.

    The transformer is stubbed out. What is under test is which snapshot reaches
    the response and whether the request survives at all, and driving the real
    schema here would only assert that pydantic still works.
    """

    def _service(self, is_carried):
        from unittest.mock import MagicMock

        service = MagicMock()
        service.is_carried = is_carried
        service.terminal_info = MagicMock()
        return service

    @pytest.fixture
    def transformed(self, monkeypatch):
        """Capture the snapshot the response would be built with."""
        from unittest.mock import MagicMock

        from app.api.v1 import cart as cart_api

        captured = {}

        def _transform(cart_doc, snapshot):
            captured["snapshot"] = snapshot
            return MagicMock(model_dump=lambda: {"signedSnapshot": snapshot})

        transformer = MagicMock()
        transformer.transform_cart = _transform
        monkeypatch.setattr(cart_api, "SchemasTransformerV1", lambda: transformer)
        return captured

    @pytest.fixture
    def cannot_sign(self, monkeypatch):
        from app.api.v1 import cart as cart_api

        monkeypatch.setattr(cart_api.snapshot_service, "build_envelope", lambda *a, **k: None)

    def _call(self, is_carried):
        from unittest.mock import MagicMock

        from app.api.v1 import cart as cart_api

        return cart_api._cart_data_with_snapshot(self._service(is_carried), MagicMock(cart_id="cart-unsigned"))

    def test_a_failure_to_sign_fails_the_request(self, transformed, cannot_sign):
        from app.exceptions import SnapshotGenerationFailedException

        with pytest.raises(SnapshotGenerationFailedException):
            self._call(is_carried=True)

        assert "snapshot" not in transformed, "an unsigned carried cart reached the response"

    def test_the_cache_path_still_answers_without_one(self, transformed, cannot_sign):
        # Nothing is lost there: the cart is in the cache and the next request
        # finds it. Failing would take a working sale down over a missing extra.
        data = self._call(is_carried=False)

        assert data["signedSnapshot"] is None
        assert transformed["snapshot"] is None

    def test_a_signed_carried_response_is_returned(self, transformed, monkeypatch):
        from app.api.v1 import cart as cart_api

        monkeypatch.setattr(cart_api.snapshot_service, "build_envelope", lambda *a, **k: {"signature": "s"})

        data = self._call(is_carried=True)

        assert data["signedSnapshot"] == {"signature": "s"}

    def test_the_failure_is_a_503_the_client_can_repeat(self, transformed, cannot_sign):
        """Repeating is the whole recovery, so the status has to say so.

        A carried request writes no cart state, so the client simply sends it
        again with the snapshot it still holds; a finalize is idempotent by
        cart_id (issue #170), so a repeat returns the transaction already
        recorded. A 4xx would tell the client to stop instead.
        """
        from fastapi import status

        from app.exceptions import SnapshotGenerationFailedException

        with pytest.raises(SnapshotGenerationFailedException) as raised:
            self._call(is_carried=True)

        assert raised.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert raised.value.error_code == "401507"


class TestTheContractIsInTheSpec:
    """A 503 nobody knows how to handle is worse than no 503 at all.

    Every other status on these routes means the request failed and the client
    may start over. This one means the opposite: on a finalize the transaction
    is already recorded, so starting a new cart books it twice. The only place a
    generated client learns that is the OpenAPI description, so it is asserted
    rather than left to survive the next edit by luck.
    """

    @pytest.fixture(scope="class")
    def schema(self):
        """Built from the router alone.

        Importing `app.main` would do it in one line, but it configures logging
        for the whole process on import and other tests then capture nothing.
        The router is what carries the declaration anyway.
        """
        from fastapi import FastAPI

        from app.api.v1 import cart as cart_api

        app = FastAPI()
        app.include_router(cart_api.router)
        return app.openapi()

    def test_every_route_that_can_return_it_declares_it(self, schema):
        from app.api.v1 import cart as cart_api

        # Derived from the router, not a hand-copied list: a new cart-mutating
        # endpoint is covered the day it is added.
        expected = {
            route.path
            for route in cart_api.router.routes
            if getattr(route, "endpoint", None) is not None
            and (
                "_cart_data_with_snapshot" in route.endpoint.__code__.co_names
                or "SnapshotGenerationFailedException" in route.endpoint.__code__.co_names
            )
        }
        assert expected, "no cart-mutating route found - the detection above stopped working"

        missing = [
            path
            for path in expected
            for method, spec in schema["paths"][path].items()
            if "503" not in spec["responses"]
        ]
        assert missing == [], missing

    def test_it_says_to_repeat_the_request(self, schema):
        description = schema["paths"]["/carts/{cart_id}/bill"]["post"]["responses"]["503"]["description"]

        assert "Repeat the identical request" in description
        assert "new cart" in description, "the description has to warn against starting over"

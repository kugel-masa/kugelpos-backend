# Copyright 2026 masa@kugel
"""The request-body ceiling holds on every service (issue #195).

FastAPI reads the body before it resolves a route's dependencies, so without a
ceiling an unauthenticated caller decides how much memory a worker spends: the
body is buffered in full and the 401 arrives after. A handful of concurrent
ones exhausts the worker, and a POS service being down means checkout is down.

These run over a real socket against the running stack, because that is what
the gap was about. The unit tests drive the middleware directly and the
in-process tests use an ASGI transport; neither shows what an actual client
gets, nor that the refusal arrives without the body being read.
"""
import os

import httpx
import pytest


# Comfortably past every service's ceiling. Services size it to their own
# traffic (issue #195): 1 MB by default, 4 MB where the largest legitimate body
# is bigger — cart carries the whole cart document on every mutating request,
# report/journal serve the Dapr tranlog subscriber from the same app, and
# master-data takes a whole item book or settings collection in one body.
OVERSIZED = 8 * 1024 * 1024

SERVICES = [
    ("account", "URL_ACCOUNT", "/api/v1/accounts/register"),
    ("terminal", "URL_TERMINAL", "/api/v1/terminals"),
    ("master-data", "URL_MASTER_DATA", "/api/v1/tenants/Z0001/stores"),
    ("cart", "URL_CART", "/api/v1/carts"),
    ("report", "URL_REPORT", "/api/v1/tenants/Z0001/stores/5678/reports"),
    ("journal", "URL_JOURNAL", "/api/v1/tenants/Z0001/journals"),
    ("stock", "URL_STOCK", "/api/v1/tenants/Z0001/stores/5678/stock"),
]


@pytest.mark.parametrize("name,url_env,path", SERVICES, ids=[s[0] for s in SERVICES])
def test_oversized_body_is_refused_by_every_service(name, url_env, path):
    """No credentials are sent: the refusal must not wait for the 401."""
    body = b'{"x": "' + b"a" * OVERSIZED + b'"}'
    with httpx.Client(base_url=os.environ[url_env], timeout=60.0) as c:
        r = c.post(path, content=body, headers={"Content-Type": "application/json"})

    assert r.status_code == 413, f"{name} answered {r.status_code}, so it read the body first"


@pytest.mark.parametrize("content_type", ["application/json", "text/plain", "application/octet-stream"])
def test_the_ceiling_does_not_depend_on_the_content_type(content_type):
    """The gap this closes was reachable by changing one header.

    The cart snapshot peel bounded only JSON bodies, so anything else was
    buffered without a limit.
    """
    body = b"a" * OVERSIZED
    with httpx.Client(base_url=os.environ["URL_CART"], timeout=60.0) as c:
        r = c.post(
            "/api/v1/carts/probe/lineItems?terminal_id=Z0001-5678-9",
            content=body,
            headers={"Content-Type": content_type},
        )

    assert r.status_code == 413, f"{content_type} was not held to the ceiling"


def test_a_body_with_no_content_type_is_refused():
    body = b"a" * OVERSIZED
    with httpx.Client(base_url=os.environ["URL_CART"], timeout=60.0) as c:
        r = c.post("/api/v1/carts/probe/lineItems?terminal_id=Z0001-5678-9", content=body)

    assert r.status_code == 413


def test_a_chunked_body_is_refused():
    """A chunked body declares no length, so the ceiling has to be read into."""

    def chunks():
        sent = 0
        while sent < OVERSIZED:
            n = min(1 << 20, OVERSIZED - sent)
            sent += n
            yield b"a" * n

    with httpx.Client(base_url=os.environ["URL_CART"], timeout=60.0) as c:
        r = c.post(
            "/api/v1/carts/probe/lineItems?terminal_id=Z0001-5678-9",
            content=chunks(),
            headers={"Content-Type": "text/plain"},
        )

    assert r.status_code == 413


def test_a_normal_request_is_unaffected():
    """The ceiling must not cost anything for a body under it.

    Rejected on its merits (401/404/422 — no credentials), which is the point:
    it reached the application rather than being refused on size.
    """
    with httpx.Client(base_url=os.environ["URL_CART"], timeout=30.0) as c:
        r = c.post(
            "/api/v1/carts/probe/lineItems?terminal_id=Z0001-5678-9",
            json=[{"itemCode": "49-01", "quantity": 1}],
        )

    assert r.status_code != 413

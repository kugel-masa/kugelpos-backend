# Copyright 2026 masa@kugel
"""Refusals generated outside the app still carry CORS headers.

CORSMiddleware was registered first and therefore ran innermost, so every
response produced further out bypassed it — the request-body 413 (#195) and
cart's compressed-body 413/415/400.

Registering it last fixes those and every app-level error, but not an
unhandled 500: Starlette builds ServerErrorMiddleware outside the whole user
middleware stack, so "outermost" only ever means outermost among the user
layers. That gap is #202, and these tests deliberately do not claim it.

A browser does not surface a response without `Access-Control-Allow-Origin`:
JS gets `TypeError: Failed to fetch`, with no status and no body. The refusal
is correct on the wire and unreadable to the client, so a browser client
cannot tell a permanent 413 (split the payload) from a transient network
error (retry) — and retries something that can never succeed.

Over a real socket, because header presence on an error path is exactly what
an in-process transport will not tell you.
"""
import os

import httpx
import pytest


ORIGIN = "https://pos.example.co.jp"

SERVICES = [
    ("account", "URL_ACCOUNT", "/api/v1/accounts/register"),
    ("terminal", "URL_TERMINAL", "/api/v1/terminals"),
    ("master-data", "URL_MASTER_DATA", "/api/v1/tenants/Z0001/stores"),
    ("cart", "URL_CART", "/api/v1/carts"),
    ("report", "URL_REPORT", "/api/v1/tenants/Z0001/stores/5678/reports"),
    ("journal", "URL_JOURNAL", "/api/v1/tenants/Z0001/journals"),
    ("stock", "URL_STOCK", "/api/v1/tenants/Z0001/stores/5678/stock"),
]

OVERSIZED = 8 * 1024 * 1024


def _allow_origin(response: httpx.Response) -> str | None:
    return response.headers.get("access-control-allow-origin")


@pytest.mark.parametrize("name,url_env,path", SERVICES, ids=[s[0] for s in SERVICES])
def test_an_oversized_body_is_refused_with_cors_headers(name, url_env, path):
    """The 413 is generated outermost, ahead of the app — and still readable."""
    body = b'{"x": "' + b"a" * OVERSIZED + b'"}'
    with httpx.Client(base_url=os.environ[url_env], timeout=60.0) as c:
        r = c.post(path, content=body, headers={"Content-Type": "application/json", "Origin": ORIGIN})

    assert r.status_code == 413, f"{name} answered {r.status_code}"
    assert _allow_origin(r) is not None, f"{name}: a browser could not read this 413"


@pytest.mark.parametrize("name,url_env,path", SERVICES, ids=[s[0] for s in SERVICES])
def test_a_normal_refusal_carries_cors_headers_too(name, url_env, path):
    """The ordering must not have been fixed only for the outermost layer."""
    with httpx.Client(base_url=os.environ[url_env], timeout=30.0) as c:
        r = c.post(path, json={}, headers={"Origin": ORIGIN})

    assert r.status_code != 413
    assert _allow_origin(r) is not None, f"{name}: {r.status_code} was unreadable to a browser"


def test_an_unsupported_content_encoding_is_refused_with_cors_headers():
    """cart's decompression middleware also sits outside CORS."""
    with httpx.Client(base_url=os.environ["URL_CART"], timeout=30.0) as c:
        r = c.post(
            "/api/v1/carts",
            content=b"not-really-zstd",
            headers={"Content-Type": "application/json", "Content-Encoding": "zstd", "Origin": ORIGIN},
        )

    assert r.status_code == 415, r.text
    assert _allow_origin(r) is not None, "a browser could not read this 415"


@pytest.mark.parametrize("name,url_env,path", SERVICES, ids=[s[0] for s in SERVICES])
def test_preflight_is_answered_without_reading_a_body(name, url_env, path):
    """Preflight now short-circuits ahead of the body ceiling, not behind it."""
    with httpx.Client(base_url=os.environ[url_env], timeout=30.0) as c:
        r = c.options(
            path,
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert r.status_code == 200, f"{name} answered preflight with {r.status_code}"
    assert _allow_origin(r) is not None


# =========================================================================
# Credentials are not allowed from a wildcard origin (issue #199)
# =========================================================================


@pytest.mark.parametrize("name,url_env,path", SERVICES, ids=[s[0] for s in SERVICES])
def test_credentials_are_not_allowed(name, url_env, path):
    """`*` and credentials together is what the CORS spec forbids.

    Starlette resolves the contradiction by echoing the caller's own Origin
    instead of returning `*`, so allow_credentials=True turned "no origin may
    send credentials" into "every origin may". Nothing here needs it —
    authentication is a bearer token or an X-API-KEY header, which a page sets
    explicitly and a hostile one cannot obtain — so it stays off.
    """
    with httpx.Client(base_url=os.environ[url_env], timeout=30.0) as c:
        r = c.post(path, json={}, headers={"Origin": ORIGIN})

    assert r.headers.get("access-control-allow-credentials") is None, (
        f"{name} still advertises credentialed cross-origin access"
    )
    # The wildcard is only safe *because* credentials are off; assert it is
    # actually being returned as a wildcard rather than an echoed origin.
    assert _allow_origin(r) == "*", f"{name} echoed an origin, which only happens with credentials on"


def test_preflight_does_not_allow_credentials_either():
    with httpx.Client(base_url=os.environ["URL_CART"], timeout=30.0) as c:
        r = c.options(
            "/api/v1/carts",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert r.status_code == 200
    assert r.headers.get("access-control-allow-credentials") is None

# Copyright 2025 masa@kugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
HTTP response compression middleware setup shared by all services.

Responses are gzip-compressed only when the client sends
``Accept-Encoding: gzip``, so clients that do not opt in are unaffected.
Request-body decompression (``Content-Encoding: gzip`` from clients) is
intentionally NOT handled here; it requires a custom ASGI middleware with
a decompressed-size guard and will be added when client-carried cart
requests need it.
"""
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

# Responses smaller than this are sent uncompressed; gzip overhead is not
# worth it below ~1KB.
GZIP_MINIMUM_SIZE_BYTES = 1024

# Level 6 is the speed/ratio sweet spot; 9 burns CPU for a few extra percent.
GZIP_COMPRESS_LEVEL = 6


def add_gzip_response_middleware(
    app: FastAPI,
    minimum_size: int = GZIP_MINIMUM_SIZE_BYTES,
    compresslevel: int = GZIP_COMPRESS_LEVEL,
) -> None:
    """
    Enable gzip compression of responses for clients that accept it.

    Must be registered AFTER the log_requests middleware (Starlette runs the
    last-added middleware outermost): log_requests JSON-parses the response
    body for the request log, so it has to observe the body before this
    middleware compresses it.

    Args:
        app: FastAPI application instance
        minimum_size: Minimum response body size in bytes to compress
        compresslevel: gzip compression level (1-9)
    """
    app.add_middleware(GZipMiddleware, minimum_size=minimum_size, compresslevel=compresslevel)

# Copyright 2026 masa@kugel
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
Authentication of what Dapr delivers to a pub/sub subscriber route (issue #134)

A daprd sidecar started with ``APP_API_TOKEN`` in its environment sends that
secret as the ``dapr-api-token`` header on every request it makes to its app,
pub/sub deliveries included. A request that reaches the app port any other
way does not carry it.

Apply the verifier to the pub/sub subscriber routes only. A route that other
services or terminals call directly, not through this app's own sidecar,
would refuse them.
"""
import hmac
from collections.abc import Awaitable, Callable
from logging import getLogger

from fastapi import HTTPException, Request, status

logger = getLogger(__name__)

DAPR_APP_TOKEN_HEADER = "dapr-api-token"


def make_dapr_app_token_verifier(expected_token: Callable[[], str]) -> Callable[[Request], Awaitable[None]]:
    """Build the FastAPI dependency that authenticates a Dapr delivery.

    Args:
        expected_token: Returns the service's ``APP_API_TOKEN``. Read on each
            request rather than captured, so that it is the service's own
            settings that decide, and a test can change them.

    Returns:
        A dependency that refuses, with 401, a request whose
        ``dapr-api-token`` header is missing or does not match. An empty
        expected token refuses every request: the settings refuse to start
        without one, and nothing should get through if they are bypassed.
    """

    async def verify_dapr_app_token(request: Request) -> None:
        expected = expected_token()
        presented = request.headers.get(DAPR_APP_TOKEN_HEADER, "")
        if expected and presented and hmac.compare_digest(presented.encode(), expected.encode()):
            return
        # A forged request gets no detail; the log says which check failed.
        logger.warning(
            f"Refused a request to {request.url.path}: "
            f"{'no APP_API_TOKEN is configured' if not expected else f'the {DAPR_APP_TOKEN_HEADER} header is missing or wrong'}"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a delivery from this service's Dapr sidecar")

    return verify_dapr_app_token

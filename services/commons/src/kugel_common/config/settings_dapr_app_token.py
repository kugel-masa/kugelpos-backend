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
Dapr app API token settings, for the services that subscribe to pub/sub

The token authenticates what Dapr delivers to this app (issue #134). It is
declared by the subscribers only (report, journal, stock), so a service that
receives nothing from Dapr does not have to be given one.
"""
from logging import getLogger

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)

#: The token the development compose file and the tests give the subscribers
#: and their sidecars. It is in the repository, so it authenticates nothing.
PUBLISHED_APP_API_TOKENS = frozenset({"dev-app-api-token-for-development-only"})


class DaprAppTokenSettings(BaseSettings):
    """
    Dapr app API token settings

    Attributes:
        APP_API_TOKEN: The secret this app's daprd sidecar sends as the
            ``dapr-api-token`` header on every pub/sub delivery. Give the app
            and its sidecar the same value; daprd reads it from its own
            environment under the same name
        ALLOW_INSECURE_DEV_SECRETS: Let the service start on the published
            development token. For the development stack and the tests only
    """
    APP_API_TOKEN: str = ""
    ALLOW_INSECURE_DEV_SECRETS: bool = False

    # A settings error reports the values it was given; these include the token.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    @model_validator(mode="after")
    def _refuse_a_missing_or_published_app_token(self):
        """Refuse to start without a token of the deployment's own (issue #134).

        The pub/sub routes carry no JWT: Dapr delivers to them as itself. They
        pick the tenant database from the event body, so anyone who can reach
        the app port could write sales, journals and stock movements into any
        tenant. The token is what tells a delivery from the sidecar apart from
        anyone else's request.

        Without one the routes refuse every delivery, which stops ingestion
        silently until the broker's retries move each event to the dead-letter
        queue; the failure belongs at startup. The development flag accepts the
        published token, never an empty one: an empty token would turn the
        check off.
        """
        token = self.APP_API_TOKEN.strip()
        if not token:
            raise ValueError(
                "APP_API_TOKEN is not set. The pub/sub routes accept only deliveries carrying it, "
                "so this service would refuse every event. Give the app and its daprd sidecar the "
                "same secret of your own, for example the output of: "
                "python -c 'import secrets; print(secrets.token_urlsafe(48))'."
            )
        if token not in PUBLISHED_APP_API_TOKENS:
            return self
        if self.ALLOW_INSECURE_DEV_SECRETS:
            logger.warning(
                "Running with the published APP_API_TOKEN: allowed by ALLOW_INSECURE_DEV_SECRETS, "
                "which only the development stack and the tests may set"
            )
            return self
        raise ValueError(
            "APP_API_TOKEN is a value published in the repository, so anyone could deliver "
            "events this service accepts. Give the app and its daprd sidecar the same secret of "
            "your own, for example the output of: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'. "
            "For the development stack and the tests only, ALLOW_INSECURE_DEV_SECRETS=true lets it start."
        )

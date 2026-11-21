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
Tenant provisioning key settings (issue #138)

POST /accounts/register creates a tenant and its superuser. It takes no user
token - there is no tenant yet to have one - so it is authenticated by this
key instead, held by whoever onboards tenants.
"""
from logging import getLogger

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)

#: The key the development compose file and the tests use. It is in the
#: repository, so it authenticates nothing.
PUBLISHED_TENANT_PROVISIONING_KEYS = frozenset({"dev-tenant-provisioning-key-for-development-only"})

#: Registration is not rate limited, so the key has to resist guessing alone
MIN_TENANT_PROVISIONING_KEY_LENGTH = 32


class TenantProvisioningSettings(BaseSettings):
    """
    Tenant provisioning key settings

    Attributes:
        TENANT_PROVISIONING_KEY: The secret POST /accounts/register requires in
            the X-Provisioning-Key header
        ALLOW_INSECURE_DEV_SECRETS: Let the service start on the published
            development key. For the development stack and the tests only
    """
    TENANT_PROVISIONING_KEY: str = ""
    ALLOW_INSECURE_DEV_SECRETS: bool = False

    # A settings error reports the values it was given; these include the key.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    @model_validator(mode="after")
    def _refuse_a_missing_or_published_provisioning_key(self):
        """Refuse to start without a key of the deployment's own (issue #138).

        Registration was open to anyone: each call created a tenant, its
        databases and a superuser whose token can create the same in every other
        service. The key is what tells an onboarding call apart from anyone
        else's.

        Without one, registration would refuse every call, which is noticed only
        when a tenant cannot be onboarded; the failure belongs at startup. The
        development flag accepts the published key, never an empty one: an empty
        key would turn the check off.
        """
        key = self.TENANT_PROVISIONING_KEY
        if not key.strip():
            raise ValueError(
                "TENANT_PROVISIONING_KEY is not set. POST /accounts/register accepts only calls "
                "carrying it, so no tenant could be registered. Set a secret of your own, for example "
                "the output of: python -c 'import secrets; print(secrets.token_urlsafe(48))'."
            )
        # A header cannot carry what follows, so such a key would refuse every
        # call that sends it as configured: surrounding whitespace is stripped
        # from a header value, and a header is not reliably decoded beyond ASCII.
        if key != key.strip() or not all("!" <= ch <= "~" for ch in key):
            raise ValueError(
                "TENANT_PROVISIONING_KEY must be printable ASCII without spaces, as a header carries it. "
                "Use, for example, the output of: python -c 'import secrets; print(secrets.token_urlsafe(48))'."
            )
        if len(key) < MIN_TENANT_PROVISIONING_KEY_LENGTH:
            raise ValueError(
                f"TENANT_PROVISIONING_KEY is shorter than {MIN_TENANT_PROVISIONING_KEY_LENGTH} characters, "
                "and nothing limits how often a key can be tried. Use, for example, the output of: "
                "python -c 'import secrets; print(secrets.token_urlsafe(48))'."
            )
        if key not in PUBLISHED_TENANT_PROVISIONING_KEYS:
            return self
        if self.ALLOW_INSECURE_DEV_SECRETS:
            logger.warning(
                "Running with the published TENANT_PROVISIONING_KEY: allowed by ALLOW_INSECURE_DEV_SECRETS, "
                "which only the development stack and the tests may set"
            )
            return self
        raise ValueError(
            "TENANT_PROVISIONING_KEY is a value published in the repository, so anyone could register "
            "tenants and superusers. Set a secret of your own, for example the output of: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'. "
            "For the development stack and the tests only, ALLOW_INSECURE_DEV_SECRETS=true lets it start."
        )

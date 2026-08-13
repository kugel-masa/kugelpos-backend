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
Startup validation for inter-service URL configuration.

Every BASE_URL_* is declared in settings_web.py with a localhost default, so a
deployment that forgets one does not fail at startup: the service comes up
healthy and the first call that needs the missing URL goes to a localhost port
that nothing is listening on inside the container. That failure is reported as
a transport error three retries later, and for BASE_URL_TERMINAL it is mapped
onto "Invalid API key" by kugel_common.security, so the real cause is invisible.

Services therefore declare the settings they actually use and validate them
during startup, before serving any request.
"""
import logging
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


class RequiredServiceUrlsMissingError(Exception):
    """Raised at startup when a service URL the caller depends on was never configured."""

    def __init__(self, service_name: str, missing: list[str]):
        self.service_name = service_name
        self.missing = missing
        super().__init__(
            f"{service_name}: required service URL settings were never configured: "
            f"{', '.join(missing)}. They are falling back to the localhost defaults "
            f"in settings_web.py, which resolve to nothing inside a container. "
            f"Set them in the compose environment or the service .env file."
        )


def verify_service_urls(
    service_name: str,
    required: Iterable[str],
    advisory: Iterable[str] = (),
    settings_obj: Optional[object] = None,
) -> None:
    """
    Verify that the given settings were explicitly configured.

    "Configured" means the value came from the environment or a .env file rather
    than from the field default. pydantic-settings records that in
    `model_fields_set`, which is a stronger signal than comparing against the
    default value: a deployment may legitimately set a value that happens to
    equal the default, and that must not be reported as missing.

    Args:
        service_name: Name of the service being started, used in messages
        required: Setting names whose absence must stop startup (e.g. "BASE_URL_TERMINAL")
        advisory: Setting names whose absence is logged but does not stop startup.
            Use this for settings that only affect non-serving behaviour, such as
            TOKEN_URL, which kugel_common.security uses solely to populate the
            OpenAPI "Authorize" URL.
        settings_obj: Settings instance to inspect. Defaults to the shared
            kugel_common settings singleton, which is also what
            http_client_helper._get_service_url reads.

    Raises:
        RequiredServiceUrlsMissingError: If any name in `required` was never configured
    """
    if settings_obj is None:
        from kugel_common.config.settings import settings as settings_obj

    configured = getattr(settings_obj, "model_fields_set", set())

    missing_advisory = [name for name in advisory if name not in configured]
    if missing_advisory:
        logger.warning(
            "%s: service URL settings left at their defaults: %s",
            service_name,
            ", ".join(missing_advisory),
        )

    missing = [name for name in required if name not in configured]
    if missing:
        raise RequiredServiceUrlsMissingError(service_name, missing)

    logger.info(
        "%s: service URL settings verified: %s",
        service_name,
        ", ".join(sorted(required)) or "(none required)",
    )

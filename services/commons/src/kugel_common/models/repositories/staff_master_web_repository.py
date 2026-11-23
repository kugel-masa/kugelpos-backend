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
Staff Master Web Repository implementation

This module provides API client operations for retrieving staff information
from the backend service. It implements a repository pattern that fetches
data over HTTP rather than from a direct database connection.
"""
from typing import Optional
from urllib.parse import quote

from kugel_common.config.settings import settings
from kugel_common.enums import StaffAuthenticationFailure
from kugel_common.utils.http_client_helper import HttpClientError, get_service_client
from kugel_common.utils.service_auth import create_service_token
from kugel_common.exceptions import NotFoundException, RepositoryException, StaffAuthenticationException
from kugel_common.models.documents.staff_master_document import StaffMasterDocument
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.log_utils import mask_sensitive_data

from logging import getLogger
logger = getLogger(__name__)

# master-data's staff verification failures, by business code (issue #323).
_VERIFY_FAILURES = {
    "405701": StaffAuthenticationFailure.STAFF_NOT_FOUND,
    "405702": StaffAuthenticationFailure.PIN_REQUIRED,
    "405703": StaffAuthenticationFailure.PIN_MISMATCH,
}


def _verify_failure(error: HttpClientError) -> Optional[StaffAuthenticationFailure]:
    """The business failure a verification error carries, or None for anything else.

    Decided by the business code in the body alone, never by the HTTP status: a
    404 may mean "staff not found" or "this master-data has no such route".
    Error bodies carry ``userError``; ``user_error`` is the deprecated name.
    """
    response = getattr(error, "response", None)
    if response is None or isinstance(response, str):
        return None
    try:
        body = response.json()
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    user_error = body.get("userError") or body.get("user_error") or {}
    if not isinstance(user_error, dict):
        return None
    return _VERIFY_FAILURES.get(user_error.get("code"))

class StaffMasterWebRepository():
    """
    Repository class for fetching staff information via web API
    
    This class provides methods to retrieve staff information from a remote API endpoint.
    Unlike database repositories, this class communicates with external services
    over HTTP and transforms the JSON responses into domain models.
    """

    def __init__(
        self, 
        tenant_id: str, 
        terminal_info: TerminalInfoDocument
    ):
        """
        Initialize a new StaffMasterWebRepository instance
        
        Args:
            tenant_id: ID of the tenant to fetch staff information for
            terminal_info: Terminal information used for authentication and context
        """
        self.tenant_id = tenant_id
        self.terminal_info = terminal_info 
        self.base_url = settings.BASE_URL_MASTER_DATA
    
    async def get_staff_by_id_async(self, id: str) -> StaffMasterDocument:
        """
        Retrieve staff information by staff ID
        
        Makes an HTTP request to the master data service API to fetch staff details
        for the specified staff ID.
        
        Args:
            id: Staff ID to look up
            
        Returns:
            StaffMasterDocument: The staff information document
            
        Raises:
            NotFoundException: If the staff information cannot be found
            RepositoryException: If there's an error communicating with the API
        """
        async with get_service_client("master-data") as client:
            jwt_token = getattr(self.terminal_info, "jwt_token", None)
            if jwt_token:
                headers = {"Authorization": f"Bearer {jwt_token}"}
                params = {}
            else:
                headers = {"X-API-KEY": self.terminal_info.api_key}
                params = {"terminal_id": self.terminal_info.terminal_id}
            endpoint = f"/tenants/{self.tenant_id}/staff/{id}"
            
            # Whichever branch above ran, `headers` holds the credential
            # itself - a bearer token or the terminal's api_key (issue #211).
            logger.debug(f"endpoint: {endpoint}, params: {params}, headers: {mask_sensitive_data(headers)}")
            
            try:
                response_data = await client.get(endpoint, params=params, headers=headers)
            except Exception as e:
                if hasattr(e, 'status_code') and e.status_code == 404:
                    message = f"staff not found for id {id}"
                    raise NotFoundException(
                        message=message, 
                        collection_name="staff web", 
                        find_key=id, 
                        logger=logger, 
                        original_exception=e
                    )
                else:
                    message = f"Request error for id {id}"
                    raise RepositoryException(
                        message=message,
                        collection_name="staff web",
                        logger=logger,
                        original_exception=e
                    )
                
            # The staff record comes back with its plaintext `pin` (issue #211).
            logger.debug(f"response: {mask_sensitive_data(response_data)}")
            return StaffMasterDocument(**response_data.get("data"))

    async def verify_staff_async(self, staff_id: str, pin: Optional[str]) -> StaffMasterDocument:
        """
        Ask master-data to verify a staff member for sign-in (issue #323).

        The PIN is compared inside master-data only, which requires it only when
        the staff record has one. This calls master-data's internal endpoint with
        a service-account token; the PIN travels in the body only.

        Args:
            staff_id: The staff member's ID, as the client sent it
            pin: The PIN the client sent, or None

        Returns:
            StaffMasterDocument: The verified staff member's ID and name. It never
            carries a PIN.

        Raises:
            StaffAuthenticationException: master-data refused (405701 / 405702 / 405703)
            RepositoryException: master-data could not decide - unreachable, a 5xx,
                or an answer without one of those codes
        """
        # The staff ID comes from the client: encode it so it cannot reshape the path.
        endpoint = f"/internal/tenants/{quote(self.tenant_id, safe='')}/staff/{quote(staff_id, safe='')}/verify"
        headers = {"Authorization": f"Bearer {create_service_token(self.tenant_id, 'terminal')}"}

        async with get_service_client("master-data") as client:
            try:
                response_data = await client.post(endpoint, json={"pin": pin}, headers=headers)
            except HttpClientError as e:
                reason = _verify_failure(e)
                if reason is not None:
                    raise StaffAuthenticationException(
                        message=f"Staff verification refused: staff_id->{staff_id}, reason->{reason.value}",
                        reason=reason,
                        logger=logger,
                    ) from e
                raise RepositoryException(
                    message=f"Staff verification could not be decided: staff_id->{staff_id}",
                    collection_name="staff web",
                    logger=logger,
                    original_exception=e,
                ) from e

        data = (response_data or {}).get("data") or {}
        if not data.get("id"):
            raise RepositoryException(
                message=f"Staff verification answered without a staff record: staff_id->{staff_id}",
                collection_name="staff web",
                logger=logger,
            )
        return StaffMasterDocument(tenant_id=self.tenant_id, id=data.get("id"), name=data.get("name"))

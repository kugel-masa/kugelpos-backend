# Copyright 2026 masa@kugel
"""
Asking report to confirm a session's settlement (#343).

terminal calls report's internal endpoints with a service-account token. When
report cannot confirm the settlement for any reason other than a malformed
request, the close is refused with 406016 and nothing is written: the terminal
stays open, and closing again is safe.
"""

from logging import getLogger
from typing import Any, Optional
from urllib.parse import quote

from kugel_common.utils.http_client_helper import HttpClientError, ServiceUrlNotConfiguredError, get_service_client
from kugel_common.utils.service_auth import create_service_token

from app.exceptions import SettlementUnavailableException, TerminalCloseException

logger = getLogger(__name__)

# report freezes five daily reports while it answers. One attempt, no retry
# (HttpClientHelper's max_retries counts attempts), so a slow report holds the
# close for at most the timeout; the clerk closes again (R-7).
SETTLEMENT_TIMEOUT_SECONDS = 30
SETTLEMENT_MAX_RETRIES = 1
_MALFORMED = (400, 422)


class SettlementWebRepository:
    def __init__(self, tenant_id: str, store_code: str, terminal_no: int):
        self.tenant_id = tenant_id
        self.store_code = store_code
        self.terminal_no = terminal_no

    def _base(self) -> str:
        return (
            f"/internal/tenants/{quote(self.tenant_id, safe='')}/stores/{quote(self.store_code, safe='')}"
            f"/terminals/{self.terminal_no}"
        )

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {create_service_token(self.tenant_id, 'terminal')}"}

    async def confirm_async(self, payload: dict) -> dict:
        """
        Confirm the settlement; returns report's settlement record (camelCase).

        Raises:
            SettlementUnavailableException: report unreachable, timed out, a 5xx,
                a 404 (an older report) or 401/403 (misconfiguration)
            TerminalCloseException: report found the request malformed (400/422)
        """
        return await self._call("post", f"{self._base()}/settlements", json=payload)

    async def preview_async(self, params: dict) -> dict:
        """What confirming would record now; nothing is stored."""
        query = {k: v for k, v in params.items() if v is not None}
        return await self._call("get", f"{self._base()}/settlement-preview", params=query)

    async def _call(self, method: str, endpoint: str, **kwargs: Any) -> dict:
        what = f"settlement {method.upper()} {endpoint}"
        try:
            async with get_service_client(
                "report", timeout=SETTLEMENT_TIMEOUT_SECONDS, max_retries=SETTLEMENT_MAX_RETRIES
            ) as client:
                response = await getattr(client, method)(endpoint, headers=self._headers(), **kwargs)
        except HttpClientError as e:
            status: Optional[int] = e.status_code
            if status in _MALFORMED:
                raise TerminalCloseException(
                    message=f"report refused the {what} as malformed ({status})", logger=logger, original_exception=e
                ) from e
            raise SettlementUnavailableException(
                message=f"report could not answer the {what} (status {status})", logger=logger, original_exception=e
            ) from e
        except ServiceUrlNotConfiguredError as e:
            raise SettlementUnavailableException(
                message=f"report is not configured for the {what}", logger=logger, original_exception=e
            ) from e
        data = (response or {}).get("data")
        if not data:
            raise SettlementUnavailableException(message=f"report answered the {what} without data", logger=logger)
        return data

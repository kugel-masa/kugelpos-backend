"""
A terminal JWT may act only on the terminal in the request path.

Before the binding, a token issued to one terminal could open, close or move
cash on any other terminal in the same tenant: the path terminal_id was never
compared with the terminal the token belongs to.
"""

import pytest
from fastapi import HTTPException

from app.dependencies.get_terminal_service import (
    get_auth_context_with_path_terminal,
    get_tenant_id_with_security_wrapper,
)
from kugel_common.models.documents.terminal_info_document import TerminalInfoDocument
from kugel_common.utils.terminal_auth import create_terminal_token

OWN_TERMINAL = "T001-S001-1"
OTHER_TERMINAL = "T001-S001-2"


def _token_for(terminal_id: str) -> str:
    tenant_id, store_code, terminal_no = terminal_id.split("-")
    return create_terminal_token(
        TerminalInfoDocument(
            tenant_id=tenant_id,
            store_code=store_code,
            terminal_no=int(terminal_no),
            terminal_id=terminal_id,
        )
    )


@pytest.mark.asyncio
async def test_terminal_jwt_reaches_its_own_terminal():
    tenant_id = await get_tenant_id_with_security_wrapper(OWN_TERMINAL, None, _token_for(OWN_TERMINAL))
    assert tenant_id == "T001"


@pytest.mark.asyncio
async def test_terminal_jwt_cannot_reach_another_terminal():
    with pytest.raises(HTTPException) as exc:
        await get_tenant_id_with_security_wrapper(OTHER_TERMINAL, None, _token_for(OWN_TERMINAL))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_context_binds_terminal_jwt_to_path():
    ctx = await get_auth_context_with_path_terminal(OWN_TERMINAL, None, _token_for(OWN_TERMINAL))
    assert ctx["auth_type"] == "terminal_jwt"

    with pytest.raises(HTTPException) as exc:
        await get_auth_context_with_path_terminal(OTHER_TERMINAL, None, _token_for(OWN_TERMINAL))
    assert exc.value.status_code == 403

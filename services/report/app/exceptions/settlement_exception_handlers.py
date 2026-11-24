# Copyright 2026 masa@kugel
"""
The response for a daily report refused because a session is not settled (#343, R-16).

The shared AppException handler always answers ``data: null``. This one answers
the same envelope with the unsettled sessions in ``data``, so the caller can see
which terminals still have to be settled.
"""

from logging import getLogger

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kugel_common.schemas.api_response import ApiResponse, UserError

from app.exceptions.report_exceptions import SessionNotSettledException

logger = getLogger(__name__)


def register_settlement_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotSettledException)
    async def session_not_settled_handler(request: Request, exc: SessionNotSettledException):
        user_error_dict = exc.get_user_error() or {}
        response = ApiResponse(
            success=False,
            code=exc.status_code,
            message=exc.message,
            user_error=UserError(code=user_error_dict.get("code"), message=user_error_dict.get("message")),
            data={"unsettledSessions": exc.unsettled_sessions},
            operation="session_not_settled_handler",
        )
        logger.info(f"Daily report refused, unsettled sessions: {exc.unsettled_sessions}")
        return JSONResponse(status_code=exc.status_code, content=response.to_response_body())

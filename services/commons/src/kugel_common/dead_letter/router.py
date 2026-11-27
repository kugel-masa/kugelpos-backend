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
The dead-letter API (contracts/dead-letter-api.md).

Each subscriber mounts the same routes, giving its own database prefix, its
409 error code and its handler core. Signed-in users only (R-9): a terminal or
service-account credential is refused with 403, a missing token with 401, and a
user of another tenant with 403.
"""

from datetime import datetime
from logging import getLogger
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import Field, field_validator

from kugel_common.database import database as db_helper
from kugel_common.dead_letter.document import (
    BULK_REPLAY_MAX,
    LISTABLE_STATES,
    TOPICS,
    DeadLetterDocument,
)
from kugel_common.dead_letter.replay import (
    HandlerCore,
    OnProcessed,
    ReplayConflict,
    ReplayNotFound,
    replay_one,
    start_bulk_replay,
)
from kugel_common.dead_letter.repository import DeadLetterRepository
from kugel_common.exceptions import ServiceException
from kugel_common.exceptions.error_codes import ErrorCode
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.base_schemas import BaseSchemmaModel, Metadata
from kugel_common.security import get_user_with_token
from kugel_common.utils.log_utils import mask_loggable

logger = getLogger(__name__)


class DeadLetterSummarySchema(BaseSchemmaModel):
    store_code: Optional[str | int] = None
    terminal_no: Optional[str | int] = None
    transaction_no: Optional[str | int] = None
    business_date: Optional[str] = None
    business_counter: Optional[str | int] = None


class DeadLetterSchema(BaseSchemmaModel):
    id: str
    service: Optional[str] = None
    topic: Optional[str] = None
    event_id: str
    state: str
    summary: DeadLetterSummarySchema = DeadLetterSummarySchema()
    last_error: Optional[str] = None
    failure_count: int = 0
    dead_count: int = 0
    first_dead_at: Optional[datetime] = None
    last_dead_at: Optional[datetime] = None
    notified_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None


class DeadLetterDetailSchema(DeadLetterSchema):
    message: Optional[dict] = None


class ReplayResultSchema(BaseSchemmaModel):
    id: str
    outcome: str
    error: Optional[str] = None


class BulkReplayRequest(BaseSchemmaModel):
    ids: list[str] = Field(min_length=1, max_length=BULK_REPLAY_MAX)


class BulkReplayAccepted(BaseSchemmaModel):
    accepted: list[str]


class DiscardRequest(BaseSchemmaModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("reason is required")
        return value.strip()


def to_schema(raw: dict, with_message: bool = False):
    doc = DeadLetterDocument.from_mongo(raw)
    values = {
        "id": doc.event_id,
        "service": doc.service,
        "topic": doc.topic,
        "event_id": doc.event_id,
        "state": doc.state,
        "summary": DeadLetterSummarySchema(**(doc.summary or {})),
        "last_error": doc.last_error,
        "failure_count": doc.failure_count,
        "dead_count": doc.dead_count,
        "first_dead_at": doc.first_dead_at,
        "last_dead_at": doc.last_dead_at,
        "notified_at": doc.notified_at,
        "resolved_at": doc.resolved_at,
        "resolved_by": doc.resolved_by,
        "resolution_note": doc.resolution_note,
    }
    if with_message:
        # Stored raw for the replay; shown masked: an open/close log carries the
        # terminal document, API key included (R-15)
        return DeadLetterDetailSchema(**values, message=mask_loggable(doc.message) if doc.message else None)
    return DeadLetterSchema(**values)


def build_dead_letter_router(
    *,
    service: str,
    db_name_prefix: str,
    conflict_error_code: str,
    core: HandlerCore,
    on_processed: Optional[OnProcessed] = None,
) -> APIRouter:
    """
    Args:
        service: report / journal / stock
        db_name_prefix: The service's DB_NAME_PREFIX
        conflict_error_code: The service's code for a record that is not pending (R-10)
        core: The service's handler core
        on_processed: Tells the publisher after a replay processed the event
    """
    router = APIRouter()

    async def user_of_tenant(tenant_id: str = Path(...), user: dict = Depends(get_user_with_token)) -> dict:
        if user.get("tenant_id") != tenant_id:
            # verify_tenant_id answers 400; another tenant's user is forbidden
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this tenant is forbidden")
        return user

    async def db_of(tenant_id: str):
        return await db_helper.get_db_async(f"{db_name_prefix}_{tenant_id}")

    def not_found(event_id: str) -> ServiceException:
        return ServiceException(
            f"Dead letter not found: {event_id}",
            logger,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            user_message="Dead letter not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    def conflict(event_id: str) -> ServiceException:
        return ServiceException(
            f"Dead letter is not pending: {event_id}",
            logger,
            error_code=conflict_error_code,
            user_message="The dead letter is not pending; someone else may have handled it",
            status_code=status.HTTP_409_CONFLICT,
        )

    @router.get(
        "/tenants/{tenant_id}/dead-letters",
        response_model=ApiResponse[list[DeadLetterSchema]],
        summary="List dead letters",
    )
    async def list_dead_letters(
        tenant_id: str = Path(...),
        state: str = Query("pending", description="pending / replaying / replayed / discarded / all"),
        topic: Optional[str] = Query(None),
        notified: Optional[bool] = Query(None),
        dead_from: Optional[datetime] = Query(None),
        dead_to: Optional[datetime] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        page: int = Query(1, ge=1),
        user: dict = Depends(user_of_tenant),
    ):
        if state == "all":
            states = list(LISTABLE_STATES)
        elif state in LISTABLE_STATES:
            states = [state]
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Unknown state: {state}")
        if topic is not None and topic not in TOPICS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Unknown topic: {topic}")
        repo = DeadLetterRepository(await db_of(tenant_id))
        rows, total = await repo.list(
            states=states, topic=topic, notified=notified, dead_from=dead_from, dead_to=dead_to, limit=limit, page=page
        )
        return ApiResponse(
            success=True,
            code=status.HTTP_200_OK,
            message=f"{len(rows)} dead letter(s)",
            data=[to_schema(row) for row in rows],
            metadata=Metadata(total=total, page=page, limit=limit, sort="lastDeadAt:-1", filter={"state": state}),
            operation="list_dead_letters",
        )

    @router.get(
        "/tenants/{tenant_id}/dead-letters/{id}",
        response_model=ApiResponse[DeadLetterDetailSchema],
        summary="Get a dead letter",
    )
    async def get_dead_letter(tenant_id: str = Path(...), id: str = Path(...), user: dict = Depends(user_of_tenant)):
        raw = await DeadLetterRepository(await db_of(tenant_id)).get(id)
        if raw is None or raw.get("state") not in LISTABLE_STATES:
            raise not_found(id)
        return ApiResponse(
            success=True,
            code=status.HTTP_200_OK,
            message="Dead letter",
            data=to_schema(raw, with_message=True),
            operation="get_dead_letter",
        )

    @router.post(
        "/tenants/{tenant_id}/dead-letters/replay",
        response_model=ApiResponse[BulkReplayAccepted],
        status_code=status.HTTP_202_ACCEPTED,
        summary="Replay several dead letters in the background",
    )
    async def replay_dead_letters(
        tenant_id: str = Path(...), body: BulkReplayRequest = Body(...), user: dict = Depends(user_of_tenant)
    ):
        ids = list(dict.fromkeys(body.ids))
        start_bulk_replay(
            db=await db_of(tenant_id), event_ids=ids, user=user["username"], core=core, on_processed=on_processed
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=ApiResponse(
                success=True,
                code=status.HTTP_202_ACCEPTED,
                message=f"{len(ids)} dead letter(s) accepted for replay",
                data=BulkReplayAccepted(accepted=ids),
                operation="replay_dead_letters",
            ).model_dump(by_alias=True, mode="json"),
        )

    @router.post(
        "/tenants/{tenant_id}/dead-letters/{id}/replay",
        response_model=ApiResponse[ReplayResultSchema],
        summary="Replay a dead letter",
    )
    async def replay_dead_letter(tenant_id: str = Path(...), id: str = Path(...), user: dict = Depends(user_of_tenant)):
        try:
            result = await replay_one(
                db=await db_of(tenant_id), event_id=id, user=user["username"], core=core, on_processed=on_processed
            )
        except ReplayNotFound:
            raise not_found(id)
        except ReplayConflict:
            raise conflict(id)
        return ApiResponse(
            success=True,
            code=status.HTTP_200_OK,
            message=f"Replay {result.outcome}",
            data=ReplayResultSchema(id=result.id, outcome=result.outcome, error=result.error),
            operation="replay_dead_letter",
        )

    @router.post(
        "/tenants/{tenant_id}/dead-letters/{id}/discard",
        response_model=ApiResponse[DeadLetterSchema],
        summary="Discard a dead letter",
    )
    async def discard_dead_letter(
        tenant_id: str = Path(...),
        id: str = Path(...),
        body: DiscardRequest = Body(...),
        user: dict = Depends(user_of_tenant),
    ):
        repo = DeadLetterRepository(await db_of(tenant_id))
        raw = await repo.discard(id, user["username"], body.reason)
        if raw is None:
            existing = await repo.get(id, with_message=False)
            if existing is None or existing.get("state") not in LISTABLE_STATES:
                raise not_found(id)
            raise conflict(id)
        return ApiResponse(
            success=True,
            code=status.HTTP_200_OK,
            message="Dead letter discarded",
            data=to_schema(raw),
            operation="discard_dead_letter",
        )

    return router

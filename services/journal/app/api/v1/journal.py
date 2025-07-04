# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, Path, Depends, status, Query
from logging import getLogger
import inspect

from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.status_codes import StatusCodes

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import JournalSchema
from app.services.journal_service import JournalService
from app.dependencies.get_journal_service import get_journal_service

# Create a router instance for journal-related endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


def parse_sort(sort: str = Query(default=None, description="?sort=field1:1,field2:-1")) -> list[tuple[str, int]]:
    """
    Parse the sort query parameter into a list of field-order tuples.

    Format example: ?sort=field1:1,field2:-1
    Where 1 means ascending order and -1 means descending order.

    Args:
        sort: String representation of sort parameters

    Returns:
        list[tuple[str, int]]: List of tuples with field name and sort order
    """
    sort_list = []
    if sort is None:
        # Default sort by terminal number, business date, and receipt number
        sort_list = [("terminal_no", 1), ("business_date", 1), ("receipt_no", 1)]
    else:
        # Parse sort query parameter into list of tuples
        sort_list = [tuple(item.split(":")) for item in sort.split(",")]
        sort_list = [(field, int(order)) for field, order in sort_list]
    return sort_list


@router.post(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/journals",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def receive_journals(
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_no: str = Path(...),
    journal_data: JournalSchema = None,
    journal_service: JournalService = Depends(get_journal_service),
):
    """
    Create a new journal entry.

    This endpoint allows terminals to submit journal entries for storage and later retrieval.
    Journal entries represent receipts, cash operations, and other terminal activities.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials
        store_code: The store code from the path
        terminal_no: The terminal number from the path
        journal_data: The journal data to store
        journal_service: The injected journal service

    Returns:
        ApiResponse: Standard API response with the created journal data
    """
    logger.info(
        f"receive_journals: tenant_id->{tenant_id}, store_code->{store_code}, terminal_no->{terminal_no}, journal_data->{journal_data}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    journal = await journal_service.receive_journal_async(journal_data.model_dump())
    return_journal = SchemasTransformerV1().transform_journal_response(journal)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Transaction received successfully. tenant_id: {tenant_id}, store_code: {store_code}, terminal_no: {terminal_no}",
        data=return_journal.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/journals",
    response_model=ApiResponse[list[JournalSchema]],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: StatusCodes.get(status.HTTP_400_BAD_REQUEST),
        status.HTTP_401_UNAUTHORIZED: StatusCodes.get(status.HTTP_401_UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: StatusCodes.get(status.HTTP_403_FORBIDDEN),
        status.HTTP_422_UNPROCESSABLE_ENTITY: StatusCodes.get(status.HTTP_422_UNPROCESSABLE_ENTITY),
        status.HTTP_500_INTERNAL_SERVER_ERROR: StatusCodes.get(status.HTTP_500_INTERNAL_SERVER_ERROR),
    },
)
async def get_journals(
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminals: list[int] = Query(None),
    transaction_types: list[int] = Query(
        None,
        description="Transaction type NormalSales->101, NormalSalesCancel->-101, ReturnSales->102, VoidSales->201, VoidReturn->202, Open->301, Close->302, Cash-In->401, Cash-Out->402",
    ),
    business_date_from: str = Query(None, description="YYYYMMDD"),
    business_date_to: str = Query(None, description="YYYYMMDD"),
    generate_date_time_from: str = Query(None, description="YYYYMMDDTHHMMSS"),
    generate_date_time_to: str = Query(None, description="YYYYMMDDTHHMMSS"),
    receipt_no_from: int = Query(None),
    receipt_no_to: int = Query(None),
    keywords: list[str] = Query(None, description="Search keywords"),
    limit: int = Query(100),
    page: int = Query(1),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    journal_service: JournalService = Depends(get_journal_service),
):
    """
    Retrieve journal entries with various filtering options.

    This endpoint provides a flexible search interface for journal entries, allowing
    filtering by terminal, transaction type, date ranges, receipt numbers, and keywords.
    Results can be paginated and sorted.

    Authentication is required via token or API key. The tenant ID in the path must match
    the one in the security credentials.

    Args:
        tenant_id: The tenant identifier from the path
        tenant_id_with_security: The tenant ID from security credentials
        store_code: The store code to filter journals by
        terminals: Optional list of terminal numbers to filter by
        transaction_types: Optional list of transaction types to filter by
        business_date_from: Optional start of business date range (YYYYMMDD)
        business_date_to: Optional end of business date range (YYYYMMDD)
        generate_date_time_from: Optional start of journal creation time range (YYYYMMDDTHHMMSS)
        generate_date_time_to: Optional end of journal creation time range (YYYYMMDDTHHMMSS)
        receipt_no_from: Optional start of receipt number range
        receipt_no_to: Optional end of receipt number range
        keywords: Optional list of keywords to search for in journal text
        limit: Maximum number of results to return (default: 100)
        page: Page number for pagination (default: 1)
        sort: Sorting criteria (default: terminal_no, business_date, receipt_no)
        journal_service: The injected journal service

    Returns:
        ApiResponse[list[JournalSchema]]: Standard API response with matching journal entries
    """
    logger.info(
        f"get_journals: tenant_id->{tenant_id}, store_code->{store_code}, terminals->{terminals}, transaction_types->{transaction_types}, business_date_from->{business_date_from}, business_date_to->{business_date_to}, generate_date_time_from->{generate_date_time_from}, generate_date_time_to->{generate_date_time_to}, receipt_no_from->{receipt_no_from}, receipt_no_to->{receipt_no_to}, keywords->{keywords}, limit->{limit}, page->{page}, sort->{sort}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    paginated_result = await journal_service.get_journals_paginated_async(
        store_code=store_code,
        terminals=terminals,
        transaction_types=transaction_types,
        business_date_from=business_date_from,
        business_date_to=business_date_to,
        generate_date_time_from=generate_date_time_from,
        generate_date_time_to=generate_date_time_to,
        receipt_no_from=receipt_no_from,
        receipt_no_to=receipt_no_to,
        keywords=keywords,
        limit=limit,
        page=page,
        sort=sort,
    )
    return_journals = [SchemasTransformerV1().transform_journal_response(journal) for journal in paginated_result.data]

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"Journals found successfully. tenant_id: {tenant_id}, store_code: {store_code}",
        data=[journal.model_dump() for journal in return_journals],
        metadata=paginated_result.metadata.model_dump(),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response

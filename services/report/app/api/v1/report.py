# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import APIRouter, status, HTTPException, Query, Depends, Path
from typing import Optional
from logging import getLogger
import inspect

from kugel_common.schemas.api_response import ApiResponse
from kugel_common.security import get_tenant_id_with_security_by_query_optional, verify_tenant_id
from kugel_common.status_codes import StatusCodes
from kugel_common.exceptions import ServiceException

from app.api.v1.schemas_transformer import SchemasTransformerV1
from app.api.v1.schemas import SalesReportResponse, CategoryReportResponse, ItemReportResponse
from app.services.report_service import ReportService
from app.dependencies.get_report_service import get_report_service
from app.dependencies.get_staff_info import get_requesting_staff_id
from app.models.documents.sales_report_document import SalesReportDocument
from app.models.documents.category_report_document import CategoryReportDocument
from app.models.documents.item_report_document import ItemReportDocument
from app.models.documents.payment_report_document import PaymentReportDocument
from app.exceptions.report_exceptions import TerminalNotClosedException

# Create a router instance for report-related endpoints
router = APIRouter()

# Get a logger instance for this module
logger = getLogger(__name__)


# parse sort query parameter
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
        # Default sort by store_code in ascending order
        sort_list = [("store_code", 1)]
    else:
        # Parse sort query parameter into list of tuples
        sort_list = [tuple(item.split(":")) for item in sort.split(",")]
        sort_list = [(field, int(order)) for field, order in sort_list]
    return sort_list


# API get report for store  #  token or (api_key and terminal_id) is required
@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/reports",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Unprocessable Entity"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_report_for_store(
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    report_scope: str = Query(..., description="Scope of the report: flash, daily"),
    report_type: str = Query(..., description="Type of the report: sales, category, item"),
    business_date: str = Query(None, description="Business date for flash and daily (single date or ignored if date range is specified)"),
    business_date_from: str = Query(None, description="Start date for date range (YYYYMMDD format)"),
    business_date_to: str = Query(None, description="End date for date range (YYYYMMDD format)"),
    open_counter: int = Query(None, description="Open counter for flash and daily, None for total in business date"),
    business_counter: int = Query(None, description="Business counter for the report"),
    limit: int = Query(100, description="Limit of the number of records to return"),
    page: int = Query(1, description="Page number to return"),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    report_service: ReportService = Depends(get_report_service),
    requesting_staff_id: Optional[str] = Depends(get_requesting_staff_id),
):
    """
    Get a report for the entire store.

    This endpoint requires either a JWT token or an API key with terminal_id.
    It provides different types of reports (sales, category, item) at different
    scopes (flash, daily) for the specified store.

    Args:
        tenant_id: The tenant identifier
        tenant_id_with_security: The tenant ID extracted from security credentials
        store_code: The store code to generate a report for
        terminal_id: The terminal ID when using API key authentication
        report_scope: The time scope of the report (flash or daily)
        report_type: The type of report to generate (sales, category, item)
        business_date: The business date in YYYYMMDD format
        open_counter: Optional counter for the specific terminal session
        business_counter: Optional business counter for the report
        limit: Maximum number of records to return
        page: Page number for pagination
        sort: Sorting criteria
        report_service: Injected report service dependency

    Returns:
        ApiResponse[SalesReportResponse]: The report data wrapped in the standard API response

    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    logger.info(f"Fetching {report_type} report for tenant_id: {tenant_id}, store_code: {store_code}")
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    
    # Validate date parameters
    if business_date_from and business_date_to:
        # Date range mode
        if report_scope == "flash":
            # Flash reports are for current session only, date range not applicable
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range is not supported for flash reports. Flash reports are for the current session only."
            )
        if business_date:
            logger.warning("Both single date and date range specified, using date range")
    elif not business_date and not (business_date_from and business_date_to):
        # Neither single date nor date range specified
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either business_date or both business_date_from and business_date_to must be specified"
        )

    # Extract terminal number from terminal_id if available (format: tenant_store_terminal)
    requesting_terminal_no = None
    if terminal_id:
        try:
            parts = terminal_id.split("_")
            if len(parts) >= 3:
                requesting_terminal_no = int(parts[-1])
        except (ValueError, IndexError):
            logger.warning(f"Could not parse terminal number from terminal_id: {terminal_id}")

    try:
        # Determine if this is an API key request (terminal_id is provided)
        is_api_key_request = terminal_id is not None
        logger.info(f"Store report request - terminal_id: {terminal_id}, is_api_key_request: {is_api_key_request}")

        report_doc = await report_service.get_report_for_store_async(
            store_code=store_code,
            report_scope=report_scope,
            report_type=report_type,
            business_date=business_date,
            open_counter=open_counter,
            business_counter=business_counter,
            limit=limit,
            page=page,
            sort=sort,
            requesting_terminal_no=requesting_terminal_no,
            requesting_staff_id=requesting_staff_id,
            is_api_key_request=is_api_key_request,
            business_date_from=business_date_from,
            business_date_to=business_date_to,
        )
        # Transform based on report type
        transformer = SchemasTransformerV1()
        if isinstance(report_doc, ItemReportDocument):
            return_report = transformer.transform_item_report_response(report_doc)
        elif isinstance(report_doc, CategoryReportDocument):
            return_report = transformer.transform_category_report_response(report_doc)
        elif isinstance(report_doc, PaymentReportDocument):
            # Payment report document - use model_dump to convert to dict
            return_report = report_doc.model_dump(by_alias=False)
        elif isinstance(report_doc, dict):
            # Legacy: Payment report returns a dict directly
            return_report = report_doc
        else:
            return_report = transformer.transform_sales_report_response(report_doc)
    except TerminalNotClosedException as e:
        # Return specific error for terminals not closed
        error_response = ApiResponse(
            success=False,
            code=e.error_code,  # Use the specific error code (412101)
            message=e.user_message,  # Use the user-friendly message
            data=None,
            operation=f"{inspect.currentframe().f_code.co_name}",
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response.model_dump()
        )
    except ServiceException as e:
        # Handle other service exceptions
        error_response = ApiResponse(
            success=False,
            code=e.error_code if hasattr(e, 'error_code') else "500001",
            message=e.user_message if hasattr(e, 'user_message') else str(e),
            data=None,
            operation=f"{inspect.currentframe().f_code.co_name}",
        )
        raise HTTPException(
            status_code=e.status_code if hasattr(e, 'status_code') else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )
    except Exception as e:
        message = (
            f"Failed to fetch {report_type} report for tenant_id: {tenant_id}, store_code: {store_code}, Error: {e}"
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"{report_type.capitalize()} report fetched successfully",
        data=return_report if isinstance(return_report, dict) else return_report.model_dump(by_alias=True),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response


def make_terminal_id(terminal_no: str = Path(...), store_code: str = Path(...), tenant_id: str = Path(...)):
    """
    Create a composite terminal ID from its components.

    Args:
        terminal_no: The terminal number
        store_code: The store code
        tenant_id: The tenant identifier

    Returns:
        str: A composite terminal ID in the format "tenant_id_store_code_terminal_no"
    """
    return f"{tenant_id}_{store_code}_{terminal_no}"


# API get report for terminal  #  token or (api_key and terminal_id) is required
@router.get(
    "/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Unprocessable Entity"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal Server Error"},
    },
)
async def get_report_for_terminal(
    tenant_id: str = Path(...),
    tenant_id_with_security: str = Depends(get_tenant_id_with_security_by_query_optional),
    store_code: str = Path(...),
    terminal_no: int = Path(...),
    terminal_id: str = Query(None, description="Terminal ID for api_key, None for token"),
    report_scope: str = Query(..., description="Scope of the report: flash, daily"),
    report_type: str = Query(..., description="Type of the report: sales, category, item"),
    business_date: str = Query(None, description="Business date for flash and daily (single date or ignored if date range is specified)"),
    business_date_from: str = Query(None, description="Start date for date range (YYYYMMDD format)"),
    business_date_to: str = Query(None, description="End date for date range (YYYYMMDD format)"),
    open_counter: int = Query(None, description="Open counter for flash and daily, None for total in business date"),
    business_counter: int = Query(None, description="Business counter for the report"),
    limit: int = Query(100, description="Limit of the number of records to return"),
    page: int = Query(1, description="Page number to return"),
    sort: list[tuple[str, int]] = Depends(parse_sort),
    report_service: ReportService = Depends(get_report_service),
    requesting_staff_id: Optional[str] = Depends(get_requesting_staff_id),
):
    """
    Get a report for a specific terminal.

    This endpoint requires either a JWT token or an API key with terminal_id.
    It provides different types of reports (sales, category, item) at different
    scopes (flush, daily) for the specified terminal.

    Args:
        tenant_id: The tenant identifier
        tenant_id_with_security: The tenant ID extracted from security credentials
        store_code: The store code
        terminal_no: The terminal number to generate a report for
        report_scope: The time scope of the report (flash or daily)
        report_type: The type of report to generate (sales, category, item)
        business_date: The business date in YYYYMMDD format
        open_counter: Optional counter for the specific terminal session
        business_counter: Optional business counter for the report
        limit: Maximum number of records to return
        page: Page number for pagination
        sort: Sorting criteria
        report_service: Injected report service dependency

    Returns:
        ApiResponse[SalesReportResponse]: The report data wrapped in the standard API response

    Raises:
        HTTPException: For various error conditions with appropriate status codes
    """
    logger.info(
        f"Fetching {report_type} report for tenant_id: {tenant_id}, store_code: {store_code}, terminal_no: {terminal_no}"
    )
    verify_tenant_id(tenant_id, tenant_id_with_security, logger)
    
    # Validate date parameters
    if business_date_from and business_date_to:
        # Date range mode
        if report_scope == "flash":
            # Flash reports are for current session only, date range not applicable
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date range is not supported for flash reports. Flash reports are for the current session only."
            )
        if business_date:
            logger.warning("Both single date and date range specified, using date range")
    elif not business_date and not (business_date_from and business_date_to):
        # Neither single date nor date range specified
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either business_date or both business_date_from and business_date_to must be specified"
        )

    try:
        # For terminal-specific reports, extract requesting terminal from terminal_id if available
        requesting_terminal_no = None
        if terminal_id:
            try:
                parts = terminal_id.split("_")
                if len(parts) >= 3:
                    requesting_terminal_no = int(parts[-1])
            except (ValueError, IndexError):
                logger.warning(f"Could not parse terminal number from terminal_id: {terminal_id}")

        # If no terminal_id (JWT auth), use the terminal_no from the path
        if requesting_terminal_no is None:
            requesting_terminal_no = terminal_no

        # Determine if this is an API key request (terminal_id is provided)
        is_api_key_request = terminal_id is not None
        logger.info(f"Terminal report request - terminal_id: {terminal_id}, is_api_key_request: {is_api_key_request}")

        report_doc = await report_service.get_report_for_terminal_async(
            store_code=store_code,
            terminal_no=terminal_no,
            report_scope=report_scope,
            report_type=report_type,
            business_date=business_date,
            open_counter=open_counter,
            business_counter=business_counter,
            limit=limit,
            page=page,
            sort=sort,
            requesting_staff_id=requesting_staff_id,
            requesting_terminal_no=requesting_terminal_no,
            is_api_key_request=is_api_key_request,
            business_date_from=business_date_from,
            business_date_to=business_date_to,
        )
        # Transform based on report type
        transformer = SchemasTransformerV1()
        if isinstance(report_doc, ItemReportDocument):
            return_report = transformer.transform_item_report_response(report_doc)
        elif isinstance(report_doc, CategoryReportDocument):
            return_report = transformer.transform_category_report_response(report_doc)
        elif isinstance(report_doc, PaymentReportDocument):
            # Payment report document - use model_dump to convert to dict
            return_report = report_doc.model_dump(by_alias=False)
        elif isinstance(report_doc, dict):
            # Legacy: Payment report returns a dict directly
            return_report = report_doc
        else:
            return_report = transformer.transform_sales_report_response(report_doc)
    except TerminalNotClosedException as e:
        # Return specific error for terminal not closed
        error_response = ApiResponse(
            success=False,
            code=e.error_code,  # Use the specific error code (412101)
            message=e.user_message,  # Use the user-friendly message
            data=None,
            operation=f"{inspect.currentframe().f_code.co_name}",
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=error_response.model_dump()
        )
    except ServiceException as e:
        # Handle other service exceptions
        error_response = ApiResponse(
            success=False,
            code=e.error_code if hasattr(e, 'error_code') else "500001",
            message=e.user_message if hasattr(e, 'user_message') else str(e),
            data=None,
            operation=f"{inspect.currentframe().f_code.co_name}",
        )
        raise HTTPException(
            status_code=e.status_code if hasattr(e, 'status_code') else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump()
        )
    except Exception as e:
        message = f"Failed to fetch {report_type} report for tenant_id: {tenant_id}, store_code: {store_code}, terminal_no: {terminal_no}, Error: {e}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    response = ApiResponse(
        success=True,
        code=status.HTTP_200_OK,
        message=f"{report_type.capitalize()} report fetched successfully",
        data=return_report if isinstance(return_report, dict) else return_report.model_dump(by_alias=True),
        operation=f"{inspect.currentframe().f_code.co_name}",
    )
    return response

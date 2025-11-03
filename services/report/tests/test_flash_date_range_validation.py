import pytest
from httpx import AsyncClient
from kugel_common.utils.service_auth import create_service_token


@pytest.mark.asyncio
async def test_flash_report_rejects_date_range_store(http_client: AsyncClient):
    """Test that flash reports reject date range parameters for store reports."""
    # Prepare test data
    tenant_id = "T9999"
    store_code = "S001"
    business_date_from = "20240101"
    business_date_to = "20240107"
    
    # Create JWT token for authorization
    service_token = create_service_token(tenant_id, "report")
    headers = {"Authorization": f"Bearer {service_token}"}
    
    # Test sales flash report with date range - should fail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
            "open_counter": 1
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    # Check either "detail" or "message" field depending on response format
    error_message = response_json.get("detail") or response_json.get("message", "")
    assert "Date range is not supported for flash reports" in error_message
    
    # Test category flash report with date range - should fail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "category",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
            "open_counter": 1
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    # Check either "detail" or "message" field depending on response format
    error_message = response_json.get("detail") or response_json.get("message", "")
    assert "Date range is not supported for flash reports" in error_message
    
    # Test item flash report with date range - should fail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "item",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
            "open_counter": 1
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    # Check either "detail" or "message" field depending on response format
    error_message = response_json.get("detail") or response_json.get("message", "")
    assert "Date range is not supported for flash reports" in error_message


@pytest.mark.asyncio
async def test_flash_report_rejects_date_range_terminal(http_client: AsyncClient):
    """Test that flash reports reject date range parameters for terminal reports."""
    # Prepare test data
    tenant_id = "T9999"
    store_code = "S001"
    terminal_no = 1
    business_date_from = "20240101"
    business_date_to = "20240107"
    
    # Create JWT token for authorization
    service_token = create_service_token(tenant_id, "report")
    headers = {"Authorization": f"Bearer {service_token}"}
    
    # Test sales flash report with date range - should fail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
            "open_counter": 1
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    # Check either "detail" or "message" field depending on response format
    error_message = response_json.get("detail") or response_json.get("message", "")
    assert "Date range is not supported for flash reports" in error_message
    
    # Test category flash report with date range - should fail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "report_scope": "flash",
            "report_type": "category",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
            "open_counter": 1
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    # Check either "detail" or "message" field depending on response format
    error_message = response_json.get("detail") or response_json.get("message", "")
    assert "Date range is not supported for flash reports" in error_message
    
    # Test item flash report with date range - should fail
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/terminals/{terminal_no}/reports",
        params={
            "report_scope": "flash",
            "report_type": "item",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to,
            "open_counter": 1
        },
        headers=headers,
    )
    
    assert response.status_code == 400
    response_json = response.json()
    # Check either "detail" or "message" field depending on response format
    error_message = response_json.get("detail") or response_json.get("message", "")
    assert "Date range is not supported for flash reports" in error_message


@pytest.mark.asyncio
async def test_flash_report_accepts_single_date(http_client: AsyncClient):
    """Test that flash reports still accept single date parameter."""
    # Prepare test data
    tenant_id = "T9999"
    store_code = "S001"
    business_date = "20240101"
    
    # Create JWT token for authorization
    service_token = create_service_token(tenant_id, "report")
    headers = {"Authorization": f"Bearer {service_token}"}
    
    # Test sales flash report with single date - should succeed (or fail for other reasons, not date validation)
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "flash",
            "report_type": "sales",
            "business_date": business_date,
            "open_counter": 1
        },
        headers=headers,
    )
    
    # Should not fail with date range error
    if response.status_code == 400:
        assert "Date range is not supported" not in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_daily_report_accepts_date_range(http_client: AsyncClient):
    """Test that daily reports still accept date range parameters."""
    # Prepare test data
    tenant_id = "T9999"
    store_code = "S001"
    business_date_from = "20240101"
    business_date_to = "20240107"
    
    # Create JWT token for authorization
    service_token = create_service_token(tenant_id, "report")
    headers = {"Authorization": f"Bearer {service_token}"}
    
    # Test sales daily report with date range - should not fail with date validation error
    response = await http_client.get(
        f"/api/v1/tenants/{tenant_id}/stores/{store_code}/reports",
        params={
            "report_scope": "daily",
            "report_type": "sales",
            "business_date_from": business_date_from,
            "business_date_to": business_date_to
        },
        headers=headers,
    )
    
    # Should not fail with flash report date range error
    if response.status_code == 400:
        assert "Date range is not supported for flash reports" not in response.json().get("detail", "")
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HTTP Helper Module
Provides generic functions for calling APIs of other microservices
"""
import logging
import time
import asyncio
import httpx
from typing import Dict, Any, Optional, Union, Tuple, Awaitable, AsyncIterator
from contextlib import asynccontextmanager

from kugel_common.config.settings import settings
from kugel_common.utils.log_utils import mask_sensitive_data

logger = logging.getLogger(__name__)

class HttpClientError(Exception):
    """Exception class for HTTP client errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class ServiceUrlNotConfiguredError(Exception):
    """
    Raised when a service name cannot be resolved to a BASE_URL_* setting.

    Deliberately NOT a subclass of HttpClientError: a missing configuration is
    not a transport failure, and callers that map HttpClientError onto an auth
    rejection (see kugel_common.security.get_terminal_info_from_terminal_service)
    would otherwise report a misconfiguration as an invalid API key.
    """
    def __init__(self, service_name: str, setting_name: str):
        self.service_name = service_name
        self.setting_name = setting_name
        super().__init__(
            f"No URL configured for service '{service_name}': "
            f"setting '{setting_name}' is not defined"
        )


class HttpClientHelper:
    """Helper class for sending HTTP requests asynchronously"""

    def __init__(self, base_url: str = "", timeout: int = 30, max_retries: int = 3, 
                 retry_delay: int = 1, headers: Optional[Dict[str, str]] = None):
        """
        Constructor for HttpClientHelper class
        
        Args:
            base_url: Base URL for the API (e.g., "http://localhost:8000")
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            headers: Default HTTP headers
        """
        self.base_url = base_url.rstrip('/') if base_url else ""
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = headers or {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Create async client
        self.client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        self._closed = False # Flag to track if the client is closed

    async def __aenter__(self):
        """Async context manager enter method"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit method"""
        await self.close()
        
    async def close(self):
        """Close the client session"""
        if self.client:
            logger.debug("Closing HTTP client")
            await self.client.aclose()
            self._closed = True
    
    def __del__(self):
        """Cleanup resources when object is destroyed"""
        # We can't await in __del__, so we just warn if client wasn't properly closed
        if hasattr(self, 'client') and self.client and not getattr(self, '_closed', False):
            logger.warning("HttpClientHelper was not properly closed. Use 'async with' or 'await client.close()'")

    def _build_url(self, endpoint: str) -> str:
        """
        Build a full URL from an endpoint
        
        Args:
            endpoint: API endpoint (e.g., "/api/users")
        
        Returns:
            Complete URL string
        """
        if endpoint.startswith(('http://', 'https://')):
            return endpoint
        
        endpoint = endpoint.lstrip('/')
        if self.base_url:
            return f"{self.base_url}/{endpoint}"
        return endpoint

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Execute an HTTP request asynchronously and return the response
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            httpx.Response object
        
        Raises:
            HttpClientError: If an error occurs during request processing
        """
        url = self._build_url(endpoint)
        headers = {**self.headers, **kwargs.pop('headers', {})}
        params = kwargs.pop('params', {})
        payload = kwargs.pop('json', None)
        # Headers carry the credential itself (X-API-Key, and an
        # "Authorization: Bearer <jwt>" value IS the token) and the payload is
        # a request body like any other (issue #211).
        logger.debug(
            f"Request URL: {url}, Headers: {mask_sensitive_data(headers)}, "
            f"Params: {mask_sensitive_data(params)}, Json: {mask_sensitive_data(payload)}"
        )
        
        # Use default timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
            
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                logger.debug(f"HTTP request: {method} {url}")
                # Use async request
                response = await self.client.request(method, url, headers=headers, params=params, json=payload, **kwargs)
                
                # Check for error status codes
                if response.status_code >= 400:
                    error_msg = f"HTTP error {response.status_code}: {url}"
                    # Use WARNING level for 404 Not Found, ERROR for other status codes
                    if response.status_code == 404:
                        logger.warning(f"{error_msg} - Response: {response.text}")
                    else:
                        logger.error(f"{error_msg} - Response: {response.text}")
                    raise HttpClientError(error_msg, status_code=response.status_code, response=response)
                
                return response
                
            except httpx.TimeoutException as e:
                last_error = HttpClientError(f"Request timeout: {url}", response=str(e))
                logger.warning(f"Timeout ({attempts+1}/{self.max_retries}): {url}")
            
            except httpx.ConnectError as e:
                last_error = HttpClientError(f"Connection error: {url}", response=str(e))
                logger.warning(f"Connection error ({attempts+1}/{self.max_retries}): {url}")
            
            except httpx.RequestError as e:
                last_error = HttpClientError(f"Request error: {url}", response=str(e))
                logger.warning(f"Request error ({attempts+1}/{self.max_retries}): {url} - {str(e)}")
                
            # Wait before retry - use asyncio.sleep for async waiting
            await asyncio.sleep(self.retry_delay)
            attempts += 1
            
        # If all retries failed
        if last_error:
            logger.error(f"Retry failure ({self.max_retries} attempts): {url}")
            raise last_error
            
        raise HttpClientError(f"Unknown error: {url}")

    async def request(self, method: str, endpoint: str, **kwargs) -> Tuple[dict, int]:
        """
        Execute an HTTP request and return the JSON response and status code
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            Tuple of JSON data and status code
            
        Raises:
            HttpClientError: If an error occurs during request processing
        """
        response = await self._make_request(method, endpoint, **kwargs)
        try:
            return response.json(), response.status_code
        except ValueError:
            # For non-JSON responses
            return {"text": response.text}, response.status_code

    async def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs) -> dict:
        """
        Execute a GET request
        
        Args:
            endpoint: API endpoint
            params: URL query parameters
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            JSON response data
        """
        data, _ = await self.request('GET', endpoint, params=params, **kwargs)
        return data

    async def post(self, endpoint: str, params:Optional[Dict] = None, data: Optional[Union[Dict, Any]] = None, json: Optional[Dict] = None, **kwargs) -> dict:
        """
        Execute a POST request
        
        Args:
            endpoint: API endpoint
            params: URL query parameters
            data: Form data or string data
            json: Data to send as JSON
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            JSON response data
        """
        data, _ = await self.request('POST', endpoint, params=params, data=data, json=json, **kwargs)
        return data

    async def put(self, endpoint: str, params: Optional[Dict], data: Optional[Union[Dict, Any]] = None, json: Optional[Dict] = None, **kwargs) -> dict:
        """
        Execute a PUT request
        
        Args:
            endpoint: API endpoint
            params: URL query parameters
            data: Form data or string data
            json: Data to send as JSON
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            JSON response data
        """
        data, _ = await self.request('PUT', endpoint, params=params, data=data, json=json, **kwargs)
        return data

    async def delete(self, endpoint: str, params: Optional[Dict],  **kwargs) -> dict:
        """
        Execute a DELETE request
        
        Args:
            endpoint: API endpoint
            params: URL query parameters
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            JSON response data
        """
        data, _ = await self.request('DELETE', endpoint, params=params, **kwargs)
        return data

    async def patch(self, endpoint: str, params: Optional[Dict],  data: Optional[Union[Dict, Any]] = None, json: Optional[Dict] = None, **kwargs) -> dict:
        """
        Execute a PATCH request
        
        Args:
            endpoint: API endpoint
            params: URL query parameters
            data: Form data or string data
            json: Data to send as JSON
            **kwargs: Additional parameters to pass to the httpx library
        
        Returns:
            JSON response data
        """
        data, _ = await self.request('PATCH', endpoint, params=params, data=data, json=json, **kwargs)
        return data


# Global client pool to reuse clients
_client_pool = {}
_client_pool_lock = asyncio.Lock()

# Useful functions for inter-service communication
def create_service_client(service_name: str, **kwargs) -> HttpClientHelper:
    """
    Create an HttpClientHelper instance for communication with microservices
    
    Args:
        service_name: Name of the service (e.g., "cart", "account")
        **kwargs: Additional parameters to pass to the HttpClientHelper constructor
    
    Returns:
        Configured HttpClientHelper instance
    
    Note:
        You still need to close the client manually with: await client.close()
        Consider using get_service_client() context manager instead.
    """
    # get the base_url for service_name
    base_url = _get_service_url(service_name)
    return HttpClientHelper(base_url=base_url, **kwargs)


async def get_pooled_client(service_name: str, **kwargs) -> HttpClientHelper:
    """
    Get a shared client from the pool or create a new one if needed
    
    Args:
        service_name: Name of the service (e.g., "cart", "account")
        **kwargs: Additional parameters to pass to the HttpClientHelper constructor
    
    Returns:
        A shared HttpClientHelper instance from the pool
        
    Note:
        Do not call close() on clients obtained from this function as they are shared
    """
    # Create a key for the client pool based on service name and important kwargs
    # Headers aren't included in the key as they may contain request-specific auth tokens
    pool_key = f"{service_name}"
    
    async with _client_pool_lock:
        if pool_key not in _client_pool:
            # Create a new client and add to the pool
            base_url = _get_service_url(service_name)
            _client_pool[pool_key] = HttpClientHelper(base_url=base_url, **kwargs)
            logger.info(f"Created new pooled HTTP client for service: {service_name} (base_url: {base_url})")
        else:
            logger.debug(f"Reusing existing pooled HTTP client for service: {service_name}")

    return _client_pool[pool_key]


async def close_all_clients():
    """Close all clients in the pool"""
    async with _client_pool_lock:
        for key, client in list(_client_pool.items()):
            await client.close()
            del _client_pool[key]


@asynccontextmanager
async def get_service_client(service_name: str, **kwargs) -> AsyncIterator[HttpClientHelper]:
    """
    Async context manager for service clients - use with 'async with'
    
    Args:
        service_name: Name of the service (e.g., "cart", "account")
        **kwargs: Additional parameters to pass to the HttpClientHelper constructor
    
    Yields:
        A configured HttpClientHelper that will be automatically closed
    
    Example:
        async with get_service_client("master-data") as client:
            data = await client.get("/items")
    """
    client = create_service_client(service_name, **kwargs)
    try:
        yield client
    finally:
        await client.close()


def _get_service_url(service_name: str) -> str:
    """
    Get the service URL for a given service name

    Args:
        service_name: Name of the service (e.g. "cart", "master-data")

    Returns:
        Service URL string

    Raises:
        ServiceUrlNotConfiguredError: If no matching BASE_URL_* setting exists.
            Failing here is deliberate: returning None yields an empty base_url,
            which turns every request into a relative URL that httpx rejects with
            UnsupportedProtocol. That is an httpx.RequestError, so _make_request
            retries it three times before surfacing a generic message that names
            neither the service nor the missing setting.
    """
    setting_name = f"BASE_URL_{service_name.replace('-', '_').upper()}"
    if not hasattr(settings, setting_name):
        raise ServiceUrlNotConfiguredError(service_name, setting_name)
    return getattr(settings, setting_name)

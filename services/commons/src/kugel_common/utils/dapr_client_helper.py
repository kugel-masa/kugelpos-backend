#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dapr Client Helper Module

Provides unified client for Dapr sidecar communication using httpx.
This module supports Pub/Sub, State Store, and other Dapr building blocks
with circuit breaker pattern and automatic retry capabilities.
"""
import json
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from enum import Enum
from datetime import datetime

from kugel_common.utils.http_client_helper import HttpClientHelper, HttpClientError
from kugel_common.config.settings import settings

import logging
logger = logging.getLogger(__name__)


class DaprComponent(Enum):
    """Dapr component types"""
    PUBSUB = "pubsub"
    STATE_STORE = "statestore"
    BINDING = "bindings"
    SECRETS = "secrets"
    CONFIGURATION = "configuration"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DaprClientHelper:
    """
    Unified client for Dapr sidecar communication using httpx
    
    Features:
    - Pub/Sub operations
    - State Store operations
    - Circuit breaker pattern
    - Automatic retry with HttpClientHelper
    - Connection pooling
    """
    
    def __init__(
        self,
        dapr_http_port: int = None,
        timeout: int = 30,
        max_retries: int = 3,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: int = 60
    ):
        """
        Initialize Dapr client
        
        Args:
            dapr_http_port: Dapr HTTP port (defaults to DAPR_HTTP_PORT env var or 3500)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            circuit_breaker_threshold: Failure count to open circuit
            circuit_breaker_timeout: Seconds before attempting to close circuit
        """
        self.dapr_http_port = dapr_http_port or int(getattr(settings, 'DAPR_HTTP_PORT', 3500))
        self.base_url = f"http://localhost:{self.dapr_http_port}/v1.0"
        
        # Initialize HTTP client with retry logic
        self.client = HttpClientHelper(
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries
        )
        
        # Circuit breaker settings
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.close()
    
    # Circuit Breaker Methods
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows the request"""
        if self._circuit_state == CircuitState.CLOSED:
            return True
            
        if self._circuit_state == CircuitState.OPEN:
            if self._last_failure_time and \
               (datetime.now() - self._last_failure_time).seconds > self.circuit_breaker_timeout:
                self._circuit_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker moved to HALF_OPEN state")
                return True
            return False
            
        return True  # HALF_OPEN state
    
    def _record_success(self):
        """Record successful operation"""
        if self._circuit_state == CircuitState.HALF_OPEN:
            self._circuit_state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker CLOSED after successful operation")
    
    def _record_failure(self):
        """Record failed operation"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()
        
        if self._failure_count >= self.circuit_breaker_threshold:
            self._circuit_state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")
    
    # Pub/Sub Operations
    async def publish_event(
        self,
        pubsub_name: str,
        topic_name: str,
        event_data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Publish an event to Dapr pub/sub
        
        Args:
            pubsub_name: Name of the pub/sub component
            topic_name: Topic to publish to
            event_data: Event data to publish
            metadata: Optional metadata for the event
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self._check_circuit_breaker():
            logger.error(f"Circuit breaker OPEN - rejecting publish to {topic_name}")
            return False
        
        endpoint = f"/publish/{pubsub_name}/{topic_name}"
        
        try:
            if metadata:
                endpoint += "?" + "&".join([f"{k}={v}" for k, v in metadata.items()])
            
            await self.client.post(endpoint, json=event_data)
            self._record_success()
            logger.info(f"Successfully published event to {topic_name}")
            return True
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to publish event to {topic_name}: {e}")
            return False
    
    # State Store Operations
    async def get_state(
        self,
        store_name: str,
        key: str,
        consistency: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Optional[Any]:
        """
        Get state from Dapr state store
        
        Args:
            store_name: Name of the state store component
            key: State key
            consistency: Consistency level (eventual, strong)
            metadata: Optional metadata
            
        Returns:
            State value or None if not found
        """
        if not self._check_circuit_breaker():
            logger.error(f"Circuit breaker OPEN - rejecting get state for {key}")
            return None
        
        endpoint = f"/state/{store_name}/{key}"
        params = {}
        
        if consistency:
            params["consistency"] = consistency
        if metadata:
            params.update(metadata)
        
        try:
            # Use _make_request directly to get raw response
            response = await self.client._make_request('GET', endpoint, params=params)
            
            # Check if state exists (Dapr returns 204 No Content for non-existent keys)
            if response.status_code == 204:
                self._record_success()
                return None
                
            self._record_success()
            
            # Dapr state store returns the raw JSON value
            # Try to parse as JSON, if it fails return as text
            try:
                return response.json()
            except:
                # If response is plain text or not valid JSON
                text = response.text
                if not text:  # Empty response
                    return None
                # Try to parse as JSON string
                try:
                    return json.loads(text)
                except:
                    return text
            
        except HttpClientError as e:
            if e.status_code == 404 or e.status_code == 204:
                self._record_success()
                return None
            self._record_failure()
            logger.error(f"Failed to get state for {key}: {e}")
            return None
    
    async def save_state(
        self,
        store_name: str,
        key: str,
        value: Any,
        etag: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        consistency: Optional[str] = None
    ) -> bool:
        """
        Save state to Dapr state store
        
        Args:
            store_name: Name of the state store component
            key: State key
            value: State value
            etag: Optional etag for concurrency control
            metadata: Optional metadata
            consistency: Consistency level
            
        Returns:
            bool: True if successful
        """
        if not self._check_circuit_breaker():
            logger.error(f"Circuit breaker OPEN - rejecting save state for {key}")
            return False
        
        endpoint = f"/state/{store_name}"
        
        state_data = [{
            "key": key,
            "value": value
        }]
        
        if etag:
            state_data[0]["etag"] = etag
        if metadata:
            state_data[0]["metadata"] = metadata
        if consistency:
            state_data[0]["options"] = {"consistency": consistency}
        
        try:
            await self.client.post(endpoint, json=state_data)
            self._record_success()
            logger.info(f"Successfully saved state for {key}")
            return True
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to save state for {key}: {e}")
            return False
    
    async def delete_state(
        self,
        store_name: str,
        key: str,
        etag: Optional[str] = None,
        consistency: Optional[str] = None
    ) -> bool:
        """
        Delete state from Dapr state store
        
        Args:
            store_name: Name of the state store component
            key: State key
            etag: Optional etag for concurrency control
            consistency: Consistency level
            
        Returns:
            bool: True if successful
        """
        if not self._check_circuit_breaker():
            logger.error(f"Circuit breaker OPEN - rejecting delete state for {key}")
            return False
        
        endpoint = f"/state/{store_name}/{key}"
        params = {}
        
        if consistency:
            params["consistency"] = consistency
        
        headers = {}
        if etag:
            headers["If-Match"] = etag
        
        try:
            await self.client.delete(endpoint, params=params, headers=headers)
            self._record_success()
            logger.info(f"Successfully deleted state for {key}")
            return True
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to delete state for {key}: {e}")
            return False
    
    # Bulk Operations
    async def get_bulk_state(
        self,
        store_name: str,
        keys: List[str],
        parallelism: int = 10,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Get multiple states in bulk
        
        Args:
            store_name: Name of the state store component
            keys: List of state keys
            parallelism: Number of parallel requests
            metadata: Optional metadata
            
        Returns:
            Dict mapping keys to values
        """
        if not self._check_circuit_breaker():
            logger.error("Circuit breaker OPEN - rejecting bulk state operation")
            return {}
            
        endpoint = f"/state/{store_name}/bulk"
        
        request_data = {
            "keys": keys,
            "parallelism": parallelism
        }
        
        if metadata:
            request_data["metadata"] = metadata
        
        try:
            response = await self.client.post(endpoint, json=request_data)
            self._record_success()
            
            # Convert response to dict
            result = {}
            if isinstance(response, list):
                for item in response:
                    result[item["key"]] = item.get("data")
            
            return result
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to get bulk state: {e}")
            return {}


# Context manager for easy usage
@asynccontextmanager
async def get_dapr_client(**kwargs) -> DaprClientHelper:
    """
    Async context manager for Dapr client
    
    Usage:
        async with get_dapr_client() as client:
            await client.publish_event("pubsub", "topic", {"data": "value"})
    """
    client = DaprClientHelper(**kwargs)
    try:
        yield client
    finally:
        await client.close()


# Convenience functions for common operations
async def publish_event(
    pubsub_name: str,
    topic_name: str,
    event_data: Dict[str, Any],
    **kwargs
) -> bool:
    """Convenience function to publish a single event"""
    async with get_dapr_client() as client:
        return await client.publish_event(pubsub_name, topic_name, event_data, **kwargs)


async def get_state(store_name: str, key: str, **kwargs) -> Optional[Any]:
    """Convenience function to get a single state"""
    async with get_dapr_client() as client:
        return await client.get_state(store_name, key, **kwargs)


async def save_state(store_name: str, key: str, value: Any, **kwargs) -> bool:
    """Convenience function to save a single state"""
    async with get_dapr_client() as client:
        return await client.save_state(store_name, key, value, **kwargs)
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

"""Health check utilities for services."""

import asyncio
import time
from typing import Optional, Tuple

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from kugel_common.schemas.health import ComponentHealth, HealthStatus


class HealthChecker:
    """Health check utilities for common service dependencies."""
    
    @staticmethod
    async def check_mongodb(client: AsyncIOMotorClient, timeout: float = 5.0) -> ComponentHealth:
        """Check MongoDB connectivity.
        
        Args:
            client: MongoDB client instance
            timeout: Timeout in seconds
            
        Returns:
            ComponentHealth object with MongoDB status
        """
        start_time = time.time()
        
        try:
            # Run ping command with timeout
            await asyncio.wait_for(
                client.admin.command('ping'),
                timeout=timeout
            )
            
            response_time = int((time.time() - start_time) * 1000)
            
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time
            )
            
        except asyncio.TimeoutError:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error="MongoDB ping timeout"
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error=f"MongoDB error: {str(e)}"
            )
    
    @staticmethod
    async def check_dapr_sidecar(
        dapr_port: int = 3500,
        timeout: float = 5.0
    ) -> ComponentHealth:
        """Check Dapr sidecar health.
        
        Args:
            dapr_port: Dapr HTTP port
            timeout: Timeout in seconds
            
        Returns:
            ComponentHealth object with Dapr sidecar status
        """
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{dapr_port}/v1.0/healthz",
                    timeout=timeout
                )
                
                response_time = int((time.time() - start_time) * 1000)
                
                if response.status_code == 204:  # Dapr returns 204 No Content for healthy
                    return ComponentHealth(
                        status=HealthStatus.HEALTHY,
                        response_time_ms=response_time
                    )
                else:
                    return ComponentHealth(
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time,
                        error=f"Dapr sidecar returned status {response.status_code}"
                    )
                    
        except httpx.TimeoutException:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error="Dapr sidecar health check timeout"
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error=f"Dapr sidecar error: {str(e)}"
            )
    
    @staticmethod
    async def check_dapr_pubsub(
        pubsub_name: str = "pubsub",
        topic: str = "health-check",
        dapr_port: int = 3500,
        timeout: float = 5.0
    ) -> ComponentHealth:
        """Check Dapr pub/sub functionality.
        
        Args:
            pubsub_name: Dapr pub/sub component name
            topic: Test topic name
            dapr_port: Dapr HTTP port
            timeout: Timeout in seconds
            
        Returns:
            ComponentHealth object with Dapr pub/sub status
        """
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                # Publish a test message
                response = await client.post(
                    f"http://localhost:{dapr_port}/v1.0/publish/{pubsub_name}/{topic}",
                    json={"test": "health-check", "timestamp": time.time()},
                    timeout=timeout
                )
                
                response_time = int((time.time() - start_time) * 1000)
                
                if response.status_code in (200, 204):
                    return ComponentHealth(
                        status=HealthStatus.HEALTHY,
                        response_time_ms=response_time,
                        component=pubsub_name
                    )
                else:
                    return ComponentHealth(
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time,
                        component=pubsub_name,
                        error=f"Pub/sub returned status {response.status_code}"
                    )
                    
        except httpx.TimeoutException:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                component=pubsub_name,
                error="Pub/sub health check timeout"
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                component=pubsub_name,
                error=f"Pub/sub error: {str(e)}"
            )
    
    @staticmethod
    async def check_dapr_state_store(
        store_name: str = "statestore",
        test_key: str = "health-check-key",
        dapr_port: int = 3500,
        timeout: float = 5.0
    ) -> ComponentHealth:
        """Check Dapr state store functionality.
        
        Args:
            store_name: Dapr state store component name
            test_key: Test key name
            dapr_port: Dapr HTTP port
            timeout: Timeout in seconds
            
        Returns:
            ComponentHealth object with Dapr state store status
        """
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                # Write test data
                test_value = {"test": "health-check", "timestamp": time.time()}
                
                write_response = await client.post(
                    f"http://localhost:{dapr_port}/v1.0/state/{store_name}",
                    json=[{
                        "key": test_key,
                        "value": test_value
                    }],
                    timeout=timeout
                )
                
                if write_response.status_code not in (200, 204):
                    return ComponentHealth(
                        status=HealthStatus.UNHEALTHY,
                        component=store_name,
                        error=f"State store write failed with status {write_response.status_code}"
                    )
                
                # Read test data
                read_response = await client.get(
                    f"http://localhost:{dapr_port}/v1.0/state/{store_name}/{test_key}",
                    timeout=timeout
                )
                
                response_time = int((time.time() - start_time) * 1000)
                
                if read_response.status_code == 200:
                    # Clean up test data (fire and forget)
                    asyncio.create_task(
                        client.delete(
                            f"http://localhost:{dapr_port}/v1.0/state/{store_name}/{test_key}"
                        )
                    )
                    
                    return ComponentHealth(
                        status=HealthStatus.HEALTHY,
                        response_time_ms=response_time,
                        component=store_name
                    )
                else:
                    return ComponentHealth(
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time,
                        component=store_name,
                        error=f"State store read failed with status {read_response.status_code}"
                    )
                    
        except httpx.TimeoutException:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                component=store_name,
                error="State store health check timeout"
            )
        except Exception as e:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                component=store_name,
                error=f"State store error: {str(e)}"
            )
    
    @staticmethod
    def determine_overall_status(checks: dict) -> HealthStatus:
        """Determine overall health status based on component checks.
        
        Args:
            checks: Dictionary of component health checks
            
        Returns:
            Overall health status
        """
        for check in checks.values():
            if check.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY
        
        return HealthStatus.HEALTHY
# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import FastAPI, HTTPException, status, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from logging import getLogger, config
from datetime import datetime
import platform
import os
import json

# Load logging configuration from the specified file
logging_conf_path = os.path.join(os.path.dirname(__file__), "logging.conf")
config.fileConfig(logging_conf_path)
logger = getLogger(__name__)
logger.info("Application started - stock service")

# Import the required application modules after the logger is configured  # This ensures all imported modules use the configured logger
from kugel_common.database import database as db_helper
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.health import HealthCheckResponse, HealthStatus, ComponentHealth
from kugel_common.utils.health_check import HealthChecker
from kugel_common.exceptions import register_exception_handlers
from kugel_common.middleware.log_requests import log_requests
from app.api.v1.stock import router as v1_stock_router
from app.api.v1.tenant import router as v1_tenant_router
from app.config.settings import settings
from app.utils.state_store_manager import state_store_manager
from app.services.multi_tenant_snapshot_scheduler import MultiTenantSnapshotScheduler
from app.dependencies.get_scheduler import set_scheduler
from app.dependencies.get_alert_service import set_alert_service
from app.dependencies.get_stock_service import get_db_from_tenant
from app.websocket.connection_manager import ConnectionManager
from app.services.alert_service import AlertService

# Create a FastAPI instance with API documentation URLs enabled
app = FastAPI(docs_url="/docs", redoc_url="/redoc")

# Create global instances for WebSocket support
connection_manager = ConnectionManager()
alert_service = AlertService(connection_manager)

# Enable remote debugging if DEBUG flag is set to "true"  # This allows attaching a debugger to the running service
IS_DEBUG = settings.DEBUG.lower() == "true"
if IS_DEBUG:
    import debugpy

    debug_port = settings.DEBUG_PORT
    debugpy.listen(("0.0.0.0", debug_port))
    logger.debug(f"Debugging enabled on port {debug_port}")
    debugpy.wait_for_client()


# Include API routers with appropriate prefixes for versioning  # Each router handles a specific domain of functionality
app.include_router(v1_stock_router, prefix="/api/v1")
app.include_router(v1_tenant_router, prefix="/api/v1")

# Add CORS middleware to allow cross-origin requests  # Currently configured to allow any origin, method, and header
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,  # Allow cookies to be sent with requests
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

# Add middleware to log all HTTP requests with service name "stock"
app.middleware("http")(log_requests("stock"))

# Register global exception handlers for consistent error responses
register_exception_handlers(app)


# Define Dapr pub/sub subscription endpoints  # This tells Dapr which topics to subscribe to and which routes to invoke when messages arrive
@app.get("/dapr/subscribe")
def subscribe_topics():
    """
    Define Dapr pub/sub subscriptions for this service.

    This endpoint is called by Dapr during startup to determine which pub/sub topics
    this service should subscribe to. When a message is published to one of these topics,
    Dapr will deliver it to the specified route.

    Returns:
        list: List of subscription configurations with pubsubname, topic, and route
    """
    return [{"pubsubname": "pubsub-tranlog-report", "topic": "topic-tranlog", "route": "/api/v1/tranlog"}]


@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    Useful for health checks and API verification.

    Returns:
        dict: A welcome message with API version information
    """
    return {"message": "Welcome to Kugel-POS Stock API. supported version: v1"}


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint for monitoring service health.

    Returns:
        HealthCheckResponse: Service health status including component checks
    """
    health_checker = HealthChecker()

    # Check MongoDB
    db_client = await db_helper.get_client_async()
    mongodb_health = await health_checker.check_mongodb(db_client)

    # Check Dapr sidecar (required for state store and pub/sub)
    dapr_sidecar_health = await health_checker.check_dapr_sidecar()

    # Check Dapr state store (used for idempotent message processing)
    dapr_statestore_health = await health_checker.check_dapr_state_store(
        store_name="statestore", test_key="health-check-stock"
    )

    # Check scheduler status
    from app.dependencies.get_scheduler import get_scheduler

    scheduler = get_scheduler()
    scheduler_health = ComponentHealth(
        status=HealthStatus.HEALTHY if scheduler and scheduler.get_status()["running"] else HealthStatus.UNHEALTHY,
        message="Scheduler is running" if scheduler and scheduler.get_status()["running"] else "Scheduler not running",
        details=scheduler.get_status() if scheduler else None,
    )

    # Build health check response
    checks = {
        "mongodb": mongodb_health,
        "dapr_sidecar": dapr_sidecar_health,  # Required for statestore and pub/sub subscription
        "dapr_statestore": dapr_statestore_health,  # Used for event deduplication
        "snapshot_scheduler": scheduler_health,  # Snapshot scheduler status
    }

    overall_status = health_checker.determine_overall_status(checks)

    return HealthCheckResponse(status=overall_status, service="stock", version="1.0.0", checks=checks)


# Application startup event handler
async def startup_event():
    """
    Executes when the application starts.
    Sets up database connections and logs system information.

    This function is registered to run when FastAPI starts up
    and handles all necessary initialization tasks.
    """
    logger.info("Starting up the application")
    logger.info(f"Operating system: {platform.platform()}")
    logger.info(f"Host name: {platform.node()}")
    logger.info(f"Python version: {platform.python_version()}")

    # Set the MongoDB URI from settings and establish a connection
    logger.info("Setting up the MongoDB URI")
    db_helper.MONGODB_URI = settings.MONGODB_URI
    db_client = await db_helper.get_client_async()
    try:
        server_info = await db_client.server_info()
        logger.info(server_info)
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        raise e

    # Initialize and start the snapshot scheduler
    logger.info("Initializing snapshot scheduler...")
    scheduler = MultiTenantSnapshotScheduler()
    set_scheduler(scheduler)  # Set it for dependency injection
    try:
        await scheduler.initialize(get_db_from_tenant)
        logger.info("Snapshot scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize snapshot scheduler: {e}")
        # Don't fail the startup, just log the error

    # Start the alert service
    logger.info("Starting alert service...")
    set_alert_service(alert_service)  # Set it for dependency injection
    alert_service.start()
    logger.info("Alert service started successfully")


# Application shutdown event handler
async def close_event():
    """
    Executes when the application shuts down.
    Ensures proper cleanup of resources like database connections.

    This function is registered to run when FastAPI is shutting down
    and handles all necessary cleanup tasks.
    """
    logger.info("closing the application")

    # Stop the alert service
    logger.info("Stopping alert service...")
    await alert_service.stop()
    set_alert_service(None)  # Clear the alert service instance

    # Shutdown the snapshot scheduler
    logger.info("Shutting down snapshot scheduler...")
    from app.dependencies.get_scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler:
        scheduler.shutdown()
        set_scheduler(None)  # Clear the scheduler instance

    # Close the state store manager
    logger.info("closing state store manager...")
    await state_store_manager.close()

    # Close the database connection
    logger.info("close database connection for all tenants...")
    await db_helper.close_client_async()

    # add close tasks here
    logger.info("Application closed")


# Register the event handlers with the FastAPI application
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", close_event)

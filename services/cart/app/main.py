# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging import getLogger, config
import platform
import os

# Load logging configuration from external file
logging_conf_path = os.path.join(os.path.dirname(__file__), "logging.conf")
config.fileConfig(logging_conf_path)
logger = getLogger(__name__)
logger.info("Application started")
logger_request = getLogger("requestLogger")

# Import the required application modules after the logger is configured
from kugel_common.database import database as db_helper
from kugel_common.middleware.log_requests import log_requests
from kugel_common.exceptions import register_exception_handlers
from kugel_common.schemas.health import HealthCheckResponse, HealthStatus, ComponentHealth
from kugel_common.utils.health_check import HealthChecker
from app.config.settings import settings
from app.api.v1.cart import router as v1_cart_router
from app.api.v1.tran import router as v1_tran_router
from app.api.v1.tenant import router as v1_tenant_router
from app.api.v1.cache import router as v1_cache_router
from app.cron.republish_undelivery_message import (
    start_republish_undelivered_tranlog_job,
    shutdown_republish_undelivered_tranlog_job,
    scheduler as republish_scheduler,
)

# Create a FastAPI instance with documentation endpoints enabled
app = FastAPI(docs_url="/docs", redoc_url="/redoc")

# Enable remote debugging if debug mode is enabled in settings
IS_DEBUG = settings.DEBUG.lower() == "true"
if IS_DEBUG:
    import debugpy

    debug_port = settings.DEBUG_PORT
    debugpy.listen(("0.0.0.0", debug_port))
    logger.debug(f"Debugging enabled on port {debug_port}")
    debugpy.wait_for_client()

# Include API routers with appropriate version prefixes
app.include_router(v1_cart_router, prefix="/api/v1")
app.include_router(v1_tran_router, prefix="/api/v1")
app.include_router(v1_tenant_router, prefix="/api/v1")
app.include_router(v1_cache_router, prefix="/api/v1")

# Configure CORS (Cross-Origin Resource Sharing) to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add a middleware to log all HTTP requests to the cart service
app.middleware("http")(log_requests("cart"))

# Register global exception handlers for consistent error responses
register_exception_handlers(app)


@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message and API version information.

    Returns:
        dict: A message indicating the service name and supported API versions
    """
    return {"message": "Welcome to Kugel-POS Cart API. supoorted version: v1"}


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

    # Check Dapr state store (cart uses cartstore for caching)
    dapr_statestore_health = await health_checker.check_dapr_state_store(
        store_name="cartstore", test_key="health-check-cart"
    )

    # Check Dapr pub/sub (cart publishes to tranlog topic)
    dapr_pubsub_health = await health_checker.check_dapr_pubsub(
        pubsub_name="pubsub-tranlog-report", topic="topic-tranlog"
    )

    # Check background jobs (republish scheduler)
    try:
        scheduler_running = republish_scheduler.running
        scheduler_jobs = len(republish_scheduler.get_jobs())
        background_jobs_health = ComponentHealth(
            status=HealthStatus.HEALTHY if scheduler_running and scheduler_jobs > 0 else HealthStatus.UNHEALTHY,
            details={
                "scheduler_running": scheduler_running,
                "job_count": scheduler_jobs,
                "job_names": [job.id for job in republish_scheduler.get_jobs()] if scheduler_running else [],
            },
            error=None if scheduler_running and scheduler_jobs > 0 else "Scheduler not running or no jobs scheduled",
        )
    except Exception as e:
        background_jobs_health = ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            details={"error": str(e)},
            error=f"Failed to check scheduler status: {str(e)}",
        )

    # Build health check response
    checks = {
        "mongodb": mongodb_health,
        "dapr_sidecar": dapr_sidecar_health,  # Required for cartstore and pub/sub
        "dapr_cartstore": dapr_statestore_health,  # Active state store for caching
        "dapr_pubsub_tranlog": dapr_pubsub_health,  # Publishes transaction logs
        "background_jobs": background_jobs_health,
    }

    overall_status = health_checker.determine_overall_status(checks)

    return HealthCheckResponse(status=overall_status, service="cart", version="1.0.0", checks=checks)


# Event handler function for application startup
async def startup_event():
    """
    Application startup event handler that initializes connections and logs system information.

    This function runs when the FastAPI app starts and sets up the required connections
    and configurations before the app starts accepting requests.
    """
    logger.info("Starting up the application")
    logger.info(f"Operating system: {platform.platform()}")
    logger.info(f"Host name: {platform.node()}")
    logger.info(f"Python version: {platform.python_version()}")

    # Configure MongoDB connection using settings from config
    logger.info("Set MongoDB URI")
    db_helper.MONGODB_URI = settings.MONGODB_URI

    # start scheduler
    logger.info("Starting the scheduler for republishing undelivered tranlog messages")
    await start_republish_undelivered_tranlog_job()


# Event handler function for application shutdown
async def close_event():
    """
    Application shutdown event handler that properly closes connections.

    This function runs when the FastAPI app is shutting down and ensures
    that all connections are closed properly to prevent resource leaks.
    """
    logger.info("closing the application")

    logger.info("Closing the database connection")
    await db_helper.close_client_async()

    logger.info("Stopping the scheduler for republishing undelivered tranlog messages")
    await shutdown_republish_undelivered_tranlog_job()

    # Close all HTTP client pools to prevent resource leaks
    logger.info("Closing all HTTP client pools")
    from kugel_common.utils.http_client_helper import close_all_clients

    await close_all_clients()

    # Close Dapr state store session
    logger.info("Closing Dapr state store session")
    from app.utils.dapr_statestore_session_helper import close_dapr_statestore_session

    await close_dapr_statestore_session()

    # Note: gRPC channels in ItemMasterGrpcRepository are instance-level and created per request.
    # They will be automatically closed during garbage collection when repository instances
    # are disposed. For explicit cleanup, the close() method should be called on each instance.
    logger.info("gRPC channels will be closed during garbage collection")

    # add shutdown tasks here
    logger.info("Application closed")


# Register the event handlers with the FastAPI application
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", close_event)

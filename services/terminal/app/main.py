# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from logging import getLogger, config
import platform
import os

# Load logging configuration from the config file
logging_conf_path = os.path.join(os.path.dirname(__file__), "logging.conf")
config.fileConfig(logging_conf_path)
logger = getLogger(__name__)
logger.info("Application started")

# Import the required application modules after the logger is configured  # to ensure proper logging for all imported modules
from kugel_common.database import database as db_helper
from kugel_common.middleware.log_requests import log_requests
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.health import HealthCheckResponse, HealthStatus, ComponentHealth
from kugel_common.utils.health_check import HealthChecker
from kugel_common.exceptions import register_exception_handlers
from app.config.settings import settings
from app.api.v1.tenant import router as v1_tenant_router
from app.api.v1.terminal import router as v1_terminal_router
from app.cron.republish_undelivery_message import (
    start_republish_undelivered_terminallog_job,
    shutdown_republish_undelivered_terminallog_job,
    scheduler as republish_scheduler,
)

# Create a FastAPI instance with API documentation URLs configured
app = FastAPI(docs_url="/docs", redoc_url="/redoc")

# Enable remote debugging if DEBUG environment variable is set to "true"  # This allows attaching a debugger to the running application
IS_DEBUG = settings.DEBUG.lower() == "true"
if IS_DEBUG:
    import debugpy

    debug_port = settings.DEBUG_PORT
    debugpy.listen(("0.0.0.0", debug_port))
    logger.debug(f"Debugging enabled on port {debug_port}")
    debugpy.wait_for_client()


# Include the API routers with versioned prefixes  # This enables API versioning and proper routing of requests
app.include_router(v1_tenant_router, prefix="/api/v1")
app.include_router(v1_terminal_router, prefix="/api/v1")

# Configure CORS (Cross-Origin Resource Sharing)  # This allows the API to be accessed from different domains/origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to log all HTTP requests to the application
app.middleware("http")(log_requests("terminal"))

# Register global exception handlers to ensure consistent error responses
register_exception_handlers(app)


@app.get("/")
async def root():
    """
    Root endpoint that provides basic API information
    Returns a welcome message and supported API versions
    """
    return {"message": "Welcome to Kugel-POS Terminal API. supoorted version: v1"}


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

    # Check Dapr sidecar (required for pub/sub)
    dapr_sidecar_health = await health_checker.check_dapr_sidecar()

    # Check Dapr pub/sub for cash log events
    dapr_pubsub_cashlog_health = await health_checker.check_dapr_pubsub(
        pubsub_name="pubsub-cashlog-report", topic="topic-cashlog"
    )

    # Check Dapr pub/sub for open/close log events
    dapr_pubsub_opencloselog_health = await health_checker.check_dapr_pubsub(
        pubsub_name="pubsub-opencloselog-report", topic="topic-opencloselog"
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
        "dapr_sidecar": dapr_sidecar_health,  # Required for pub/sub publishing
        "dapr_pubsub_cashlog": dapr_pubsub_cashlog_health,  # Publishes cash in/out events
        "dapr_pubsub_opencloselog": dapr_pubsub_opencloselog_health,  # Publishes terminal open/close events
        "background_jobs": background_jobs_health,
    }

    overall_status = health_checker.determine_overall_status(checks)

    return HealthCheckResponse(
        status=overall_status,
        service="terminal",
        version="1.0.0",  # TODO: Get from __about__.py or settings
        checks=checks,
    )


# Application startup event handler
async def startup_event():
    """
    Executes when the application starts
    Initializes connections and logs system information
    """
    logger.info("Starting up the application")
    logger.info(f"Operating system: {platform.platform()}")
    logger.info(f"Host name: {platform.node()}")
    logger.info(f"Python version: {platform.python_version()}")

    # Initialize MongoDB connection
    logger.info("Set MongoDB URI")
    db_helper.MONGODB_URI = settings.MONGODB_URI
    db_client = await db_helper.get_client_async()
    try:
        server_info = await db_client.server_info()
        logger.info(server_info)
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        raise e

    # Start the republish job for undelivered terminal log messages
    await start_republish_undelivered_terminallog_job()
    logger.info("Started republish job for undelivered terminal log messages")


# Application shutdown event handler
async def close_event():
    """
    Executes when the application is shutting down
    Closes database connections and performs cleanup
    """
    logger.info("closing the application")

    # Shutdown the republish job for undelivered terminal log messages
    await shutdown_republish_undelivered_terminallog_job()
    logger.info("Shutdown republish job for undelivered terminal log messages")

    logger.info("Closing the database connection")
    await db_helper.close_client_async()

    # Add additional cleanup tasks here if needed
    logger.info("Application closed")


# Register the event handlers with the FastAPI application
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", close_event)

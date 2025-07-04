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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging import getLogger, config
import platform
import os

# Load logging configuration from the specified file
logging_conf_path = os.path.join(os.path.dirname(__file__), "logging.conf")
config.fileConfig(logging_conf_path)
logger = getLogger(__name__)
logger.info("Application started - auth service")

# Import the required application modules after the logger is configured
# This ensures all imported modules use the configured logger
from kugel_common.database import database as db_helper
from kugel_common.schemas.health import HealthCheckResponse
from kugel_common.utils.health_check import HealthChecker
from kugel_common.exceptions import register_exception_handlers
from kugel_common.middleware.log_requests import log_requests
from app.config.settings import settings
from app.api.v1.account import router as v1_account_router

# Create a FastAPI instance with API documentation URLs enabled
app = FastAPI(docs_url="/docs", redoc_url="/redoc")

# Enable remote debugging if debug mode is enabled in settings
IS_DEBUG = settings.DEBUG.lower() == "true"
if IS_DEBUG:
    import debugpy

    debug_port = settings.DEBUG_PORT
    debugpy.listen(("0.0.0.0", debug_port))
    logger.debug(f"Debugging enabled on port {debug_port}")
    debugpy.wait_for_client()

# Include the account router with the '/api/v1/accounts' prefix
app.include_router(v1_account_router, prefix="/api/v1/accounts")

# CORS (Cross-Origin Resource Sharing) configuration
# Commented out origins are for local development restrictions
# Currently allowing all origins with "*"
# origins = [
#    "http://localhost:8001",
#    "http://localhost:8002",
#    "http://localhost:8003",
# ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,  # Allow cookies to be sent with requests
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

# Add a middleware to log all HTTP requests with service name "account"
app.middleware("http")(log_requests("account"))

# Register global exception handlers for consistent error responses
register_exception_handlers(app)


@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    Useful for health checks and API verification.
    """
    return {"message": "Welcome to Kugel-POS Auth API. supoorted version: v1"}


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

    # Account service does not use any Dapr components
    # Only check MongoDB
    checks = {
        "mongodb": mongodb_health,
    }

    overall_status = health_checker.determine_overall_status(checks)

    return HealthCheckResponse(
        status=overall_status,
        service="account",
        version="1.0.0",  # TODO: Get from __about__.py or settings
        checks=checks,
    )


# Application startup event handler
async def startup_event():
    """
    Executes when the application starts.
    Sets up database connections and logs system information.
    """
    logger.info("Starting up the application")
    logger.info(f"Operating system: {platform.platform()}")
    logger.info(f"Host name: {platform.node()}")
    logger.info(f"Python version: {platform.python_version()}")

    # Set the MongoDB URI from settings and establish a connection
    logger.info("Set MongoDB URI")
    db_helper.MONGODB_URI = settings.MONGODB_URI
    db_client = await db_helper.get_client_async()
    try:
        server_info = await db_client.server_info()
        logger.info(server_info)
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        raise e

    # add startup tasks here


# Application shutdown event handler
async def close_event():
    """
    Executes when the application shuts down.
    Ensures proper cleanup of resources like database connections.
    """
    logger.info("closing the application")

    logger.info("Closing the database connection")
    await db_helper.close_client_async()

    # add close tasks here
    logger.info("Application closed")


# Register the event handlers with the FastAPI application
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", close_event)

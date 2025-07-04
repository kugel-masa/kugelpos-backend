# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
"""
KugelPOS Master-Data Service

This service provides API endpoints to manage master data for the KugelPOS system.
Master data includes configuration and reference data that is relatively static and
used by other services, such as:

- Staff information (staff details, PIN codes, roles)
- Item master data (common attributes, store-specific attributes, book-specific attributes)
- Payment method configuration
- System settings
- Category hierarchies
- Tax configuration
- Tenant management

The service follows a multi-tenant architecture where each tenant's data is isolated,
and access is controlled through authentication and authorization mechanisms.

The API is RESTful and uses JSON for data exchange. All endpoints return a standardized
ApiResponse object which includes success status, data, and error information when applicable.
"""

from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from logging import getLogger, config
import platform
import os

# Load logging configuration from the specified file
logging_conf_path = os.path.join(os.path.dirname(__file__), "logging.conf")
config.fileConfig(logging_conf_path)
logger = getLogger(__name__)
logger.info("Application started - master_data service")

# Import the required application modules after the logger is configured  # This ensures all imported modules use the configured logger
from kugel_common.database import database as db_helper
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.health import HealthCheckResponse, HealthStatus, ComponentHealth
from kugel_common.utils.health_check import HealthChecker
from kugel_common.exceptions import register_exception_handlers
from kugel_common.middleware.log_requests import log_requests

# Import routers for different types of master data
from app.api.v1.staff_master import router as v1_staff_master_router
from app.api.v1.item_common_master import router as v1_item_common_master_router
from app.api.v1.item_store_master import router as v1_item_store_master_router
from app.api.v1.item_book_master import router as v1_item_book_master_router
from app.api.v1.payment_master import router as v1_payment_master_router
from app.api.v1.settings_master import router as v1_settings_master_router
from app.api.v1.category_master import router as v1_category_master_router
from app.api.v1.tenant import router as v1_tenant_router
from app.api.v1.tax_master import router as v1_tax_master_router
from app.config.settings import settings

# Create a FastAPI instance with API documentation URLs enabled
app = FastAPI(
    title="KugelPOS Master-Data Service",
    description="Service for managing master data in the KugelPOS system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS (Cross-Origin Resource Sharing) to allow requests from any origin  # This is important for allowing web frontends to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,  # Allow cookies to be sent with requests
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

# Include all the routers with the /api/v1 prefix for versioning  # Each router handles a specific type of master data
app.include_router(
    v1_staff_master_router, prefix="/api/v1", tags=["Staff Master"]
)  # Staff information management (staff details, roles, PINs)

app.include_router(
    v1_item_common_master_router, prefix="/api/v1", tags=["Item Common Master"]
)  # Common item data (shared across all stores)

app.include_router(
    v1_item_store_master_router, prefix="/api/v1", tags=["Item Store Master"]
)  # Store-specific item data (prices, inventory)

app.include_router(
    v1_item_book_master_router, prefix="/api/v1", tags=["Item Book Master"]
)  # Book-specific item data (ISBN, author, publisher)

app.include_router(
    v1_payment_master_router, prefix="/api/v1", tags=["Payment Master"]
)  # Payment method configuration (cash, credit card, etc.)

app.include_router(
    v1_settings_master_router, prefix="/api/v1", tags=["Settings Master"]
)  # System settings configuration

app.include_router(
    v1_category_master_router, prefix="/api/v1", tags=["Category Master"]
)  # Item category hierarchy management

app.include_router(v1_tenant_router, prefix="/api/v1", tags=["Tenant"])  # Tenant management operations

app.include_router(v1_tax_master_router, prefix="/api/v1", tags=["Tax Master"])  # Tax configuration (rates, rules)

# Add middleware to log all HTTP requests with service name "master-data"
app.middleware("http")(log_requests("master-data"))

# Register global exception handlers for consistent error responses
register_exception_handlers(app)


@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint that returns a welcome message.

    This endpoint serves as a simple health check to verify that the service is running
    and responding to requests. It can be used by monitoring tools or load balancers
    to determine if the service is available.

    Returns:
        dict: A welcome message with API version information
    """
    logger.info("Root request received")
    return {"message": "Welcome to Kugel-POS Master-data Service API. supoorted version: v1"}


@app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
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

    # Master-data service does not use any Dapr components
    # Only check MongoDB

    # Build health check response
    checks = {
        "mongodb": mongodb_health,
    }

    overall_status = health_checker.determine_overall_status(checks)

    return HealthCheckResponse(status=overall_status, service="master-data", version="1.0.0", checks=checks)


# Application startup event handler
async def startup_event():
    """
    Executes when the application starts.

    This event handler performs the following tasks:
    1. Logs system information (OS, hostname, Python version)
    2. Configures the MongoDB connection using settings
    3. Verifies database connectivity by requesting server info
    4. Performs any additional startup tasks

    If database connection fails, the application will not start and will log an error.

    Raises:
        Exception: If there is an error connecting to the database
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

    This event handler performs the following tasks:
    1. Logs that the application is shutting down
    2. Closes the database connections to prevent connection leaks
    3. Performs any additional cleanup tasks

    This ensures that all resources are properly released when the application terminates.
    """
    logger.info("closing the application")

    logger.info("Closing the database connection")
    await db_helper.close_client_async()

    # add shutdown tasks here
    logger.info("Application closed")


# Register the event handlers with the FastAPI application
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", close_event)

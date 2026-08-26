# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
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
logger.info("Application started - journal service")

# Import the required application modules after the logger is configured  # This ensures all imported modules use the configured logger
from kugel_common.database import database as db_helper
from kugel_common.schemas.api_response import ApiResponse
from kugel_common.schemas.health import HealthCheckResponse, HealthStatus, ComponentHealth
from kugel_common.utils.health_check import HealthChecker
from kugel_common.exceptions import register_exception_handlers
from kugel_common.middleware.log_requests import log_requests
from kugel_common.middleware.http_compression import add_gzip_response_middleware
from kugel_common.middleware.request_body_limit import add_request_body_limit_middleware
from kugel_common.middleware.unhandled_error import add_unhandled_error_middleware
from kugel_common.exceptions.error_codes import ErrorCode
from kugel_common.config.service_urls import verify_service_urls
from app.api.v1.tenant import router as v1_tenant_router
from app.api.v1.journal import router as v1_journal_router
from app.api.v1.tran import router as v1_tran_router
from app.config.settings import settings

# Create a FastAPI instance with API documentation URLs enabled
# Inter-service URL settings this service actually reads. Verified during
# startup so a deployment that omits one fails here instead of serving
# traffic that dies on a localhost default three retries later (#159).
REQUIRED_SERVICE_URLS = [
    "BASE_URL_TERMINAL",
    "BASE_URL_CART",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_service_urls("journal", REQUIRED_SERVICE_URLS, advisory=["TOKEN_URL"])
    await startup_event()
    yield
    await close_event()


app = FastAPI(lifespan=lifespan, docs_url="/docs", redoc_url="/redoc")

# Enable remote debugging if DEBUG flag is set to "true"  # This allows attaching a debugger to the running service
IS_DEBUG = settings.DEBUG.lower() == "true"
if IS_DEBUG:
    import debugpy

    debug_port = settings.DEBUG_PORT
    debugpy.listen(("0.0.0.0", debug_port))
    logger.debug(f"Debugging enabled on port {debug_port}")
    debugpy.wait_for_client()

# Include API routers with appropriate prefixes for versioning  # Each router handles a specific domain of functionality
app.include_router(v1_journal_router, prefix="/api/v1")  # Journal generation endpoints
app.include_router(v1_tenant_router, prefix="/api/v1")  # Tenant management endpoints
app.include_router(v1_tran_router, prefix="/api/v1")  # Transaction processing endpoints

# Add middleware to log all HTTP requests with service name "journal"
app.middleware("http")(log_requests("journal"))

# Compress responses for clients that send Accept-Encoding: gzip.
# Registered after log_requests so compression runs outermost and the
# request log still observes the uncompressed body.
add_gzip_response_middleware(app)

# Bound the request body this service will hold (issue #195). Registered LAST so
# it runs OUTERMOST: FastAPI reads the body before it resolves a route's
# dependencies, so without this an unauthenticated caller decides how much
# memory the worker spends and the 401 arrives only after the body is held.
add_request_body_limit_middleware(
    app,
    max_bytes=settings.MAX_REQUEST_BODY_BYTES,
    error_code=ErrorCode.REQUEST_BODY_TOO_LARGE,
)

# Answer an unhandled exception from inside CORS (issue #202). Registered
# immediately before CORS so it runs just inside it: Starlette builds
# ServerErrorMiddleware around the whole user stack, so without this the 500
# is emitted outside CORS and a browser is given nothing to read.
add_unhandled_error_middleware(app)

# CORS must be registered LAST so it runs OUTERMOST (Starlette's add_middleware
# inserts at index 0, so the last registration is the outermost layer).
#
# Registered first, it ran innermost, and every response generated outside it
# bypassed it - the request-body 413 (issue #195) above all. A browser is
# handed an opaque network failure rather than the status it actually got, so
# a client cannot tell a permanent 413 (split the payload) from a transient
# error (retry).
#
# Outermost here means outermost among the USER middleware. Starlette builds
# ServerErrorMiddleware outside all of it, so an unhandled 500 still bypasses
# CORS - including this service's own generic handler, which Starlette lifts
# out of ExceptionMiddleware because it is keyed on Exception. Tracked in
# issue #202; not fixed by this ordering.
#
# Safe to sit outside the body ceiling: CORSMiddleware never touches `receive`,
# so nothing buffers ahead of the limit. Preflight OPTIONS now short-circuits
# before the body is read at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,  # Allow cookies to be sent with requests
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

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

    The journal service subscribes to transaction logs, cash logs, and open/close logs
    to generate and store journal entries for each operation.

    Returns:
        list: List of subscription configurations with pubsubname, topic, and route
    """
    return [
        {"pubsubname": "pubsub-tranlog-report", "topic": "topic-tranlog", "route": "/api/v1/tranlog"},
        {"pubsubname": "pubsub-cashlog-report", "topic": "topic-cashlog", "route": "/api/v1/cashlog"},
        {"pubsubname": "pubsub-opencloselog-report", "topic": "topic-opencloselog", "route": "/api/v1/opencloselog"},
    ]


@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    Useful for health checks and API verification.

    Returns:
        dict: A welcome message with API version information
    """
    return {"message": "Welcome to Kugel-POS Journal API. supoorted version: v1"}


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
        store_name="statestore", test_key="health-check-journal"
    )

    # Build health check response
    checks = {
        "mongodb": mongodb_health,
        "dapr_sidecar": dapr_sidecar_health,  # Required for statestore and pub/sub subscription
        "dapr_statestore": dapr_statestore_health,  # Used for event deduplication
    }

    overall_status = health_checker.determine_overall_status(checks)

    return HealthCheckResponse(status=overall_status, service="journal", version="1.0.0", checks=checks)


# Application startup event handler
async def startup_event():
    """
    Executes when the application starts.
    Sets up database connections and logs system information.

    This function is registered to run when FastAPI starts up
    and handles all necessary initialization tasks for the journal service.
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


# Application shutdown event handler
async def close_event():
    """
    Executes when the application shuts down.
    Ensures proper cleanup of resources like database connections.

    This function is registered to run when FastAPI is shutting down
    and handles all necessary cleanup tasks.
    """
    logger.info("closing the application")

    logger.info("Flushing request log buffer")
    from kugel_common.middleware.request_log_buffer import get_request_log_buffer
    await get_request_log_buffer().shutdown()

    # Close the database connection
    logger.info("close database connection for all tenants...")
    await db_helper.close_client_async()

    # add close tasks here
    logger.info("Application closed")



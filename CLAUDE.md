# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kugelpos is a microservices-based Point of Sale (POS) backend system built with FastAPI, MongoDB, and Dapr. The system consists of 7 core services that communicate via Dapr service mesh and Redis pub/sub.

## Architecture

### Core Services
- **account** (port 8000): User authentication and JWT token management
- **terminal** (port 8001): Terminal/store management and API key handling
- **master-data** (port 8002): Product catalog, payment methods, tax rules, staff management
- **cart** (port 8003): Shopping cart, transaction processing with state machine pattern
- **report** (port 8004): Sales reports and daily summaries with plugin architecture
- **journal** (port 8005): Electronic journal and transaction log storage
- **stock** (port 8006): Inventory management and stock tracking

### Key Technologies
- **Python 3.12+** with FastAPI for REST APIs
- **MongoDB** (Motor async driver) for persistence
- **Redis** for caching and pub/sub messaging
- **Dapr** for service mesh, state management, and pub/sub
- **Docker & Docker Compose** for containerization
- **Pipenv** for dependency management

## Common Development Commands

### Quick Start

```bash
# Clone the repository
git clone https://github.com/kugel-masa/kugelpos-backend.git
cd kugelpos-backend

# Prepare .env files for each service (optional - services work with defaults)
# Copy .env.sample to .env in each service directory if needed

# Prepare test environment file (change tenant ID if needed)
cp .env.test.sample .env.test

# Navigate to scripts directory
cd scripts

# Make all scripts executable
bash make_scripts_executable.sh

# Build all services
./build.sh              # Build all services
./build.sh cart journal # Build specific services
./build.sh --no-cache   # Build without cache
./build.sh --parallel   # Build in parallel

# Start all services (includes MongoDB replica set initialization)
./start.sh

# Setup development environment (for running tests)
./rebuild_pipenv.sh                    # Build Python virtual environments
./run_all_tests_with_progress.sh       # Run all tests with progress display

# Stop all services
./stop.sh

# Stop and clean all data
./scripts/stop.sh --clean
```

**Important Note**: As of version 0.0.206, services can run without .env files. The system uses:
1. Environment variables from docker-compose.override.yaml
2. Environment variables from docker-compose.yaml
3. .env files (if present)
4. Default values in settings classes

### Service Management

```bash
# From services directory
cd services

# Check service status
docker-compose ps

# View logs
docker-compose logs -f              # All services
docker-compose logs -f cart         # Specific service
docker-compose logs --tail=100 cart # Last 100 lines

# Restart a service
docker-compose restart cart

# Scale a service
docker-compose up -d --scale cart=3

# Execute commands in a running container
docker-compose exec cart bash
docker-compose exec cart pipenv run pytest
```

### Database Operations

```bash
# MongoDB operations
docker exec -it mongodb mongosh                          # Connect to MongoDB
docker exec -it mongodb mongosh --eval "rs.status()"     # Check replica set status
./scripts/reset-mongodb.sh                               # Complete MongoDB reset

# Redis operations
docker exec -it redis redis-cli                          # Connect to Redis
docker exec -it redis redis-cli FLUSHALL                 # Clear all Redis data
```

### Testing

```bash
# Run all tests for all services (from project root)
./scripts/run_all_tests.sh                    # Basic test run
./scripts/run_all_tests_with_progress.sh      # With progress display

# OR navigate to services directory for specific service tests
cd services

# Run tests for a specific service
cd cart
./run_all_tests.sh                    # Run all tests in sequence
pipenv run pytest tests/ -v           # Run all tests with pytest
pipenv run pytest tests/test_cart.py -v  # Run specific test file
pipenv run pytest tests/ -k "test_add_item" -v  # Run specific test by name

# Test with coverage
cd cart
pipenv run pytest --cov=app tests/
pipenv run pytest --cov=app --cov-report=html tests/  # With HTML report

# Run tests in Docker container (from services directory)
cd ..
docker-compose run --rm cart pipenv run pytest tests/ -v
```

### Local Development

```bash
# Navigate to services directory
cd services

# Start only infrastructure services
docker-compose up -d mongodb redis

# Run a specific service locally (example: cart service)
cd cart
pipenv install                        # Install dependencies

# Method 1: Using the run.py script (simplest)
pipenv run python run.py

# Method 2: Using uvicorn directly (for development with reload)
pipenv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8003

# Method 3: Direct execution of main.py (requires proper PYTHONPATH)
PYTHONPATH=. pipenv run python app/main.py

# Run with environment variables
MONGODB_URI=mongodb://localhost:27017/?replicaSet=rs0 pipenv run python app/main.py
```

#### Service Port Mappings
- account: port 8000
- terminal: port 8001
- master-data: port 8002
- cart: port 8003
- report: port 8004
- journal: port 8005
- stock: port 8006

### Dependency Management

```bash
# Update common library in all services (from project root)
./scripts/update_common_and_rebuild.sh

# Add new dependency
cd services/cart
pipenv install requests

# Update all dependencies
pipenv update

# Rebuild virtual environment (from project root)
./scripts/rebuild_pipenv.sh
```

### After Making Code Changes: Build and Test Procedure

When you've made code changes (especially to commons library or report service), follow these steps to build, test, and verify:

```bash
# 1. Build commons library and distribute to all services (without version increment)
./scripts/update_common_and_rebuild.sh

# 2. Rebuild Docker images for affected services
./scripts/build.sh report          # For specific service
# OR
./scripts/build.sh                 # For all services
# Optional flags:
#   --no-cache   : Build without using cache
#   --parallel   : Build in parallel

# 3. Stop all running services
./scripts/stop.sh

# 4. Start all services with health check
./scripts/start.sh

# 5. Verify services are running (from services directory)
cd services
docker-compose logs -f report      # Check specific service logs

# 6. Run tests to verify changes
cd report
./run_all_tests.sh                 # Run all tests for the service
```

**Important Notes:**
- **DO NOT** use `--increment-version` flag with `update_common_and_rebuild.sh` unless you're making actual changes to the commons library code
- Always verify service health after restart before running tests
- If porting fixes from private repository, maintain the commons version from the public repository
- The build process uses the `commons/dist/` wheel files referenced in each service's Pipfile

### Code Quality

```bash
# Navigate to specific service
cd services/cart

# Linting with ruff
pipenv run ruff check app/           # Check for issues
pipenv run ruff check --fix app/     # Auto-fix issues
pipenv run ruff format app/          # Format code

# Type checking (if configured)
pipenv run mypy app/

# Run pre-commit hooks (if configured)
pre-commit run --all-files
```

### Maintenance Scripts

```bash
# Make all shell scripts executable (useful after cloning/copying)
./scripts/make_scripts_executable.sh               # Entire project (default)
./scripts/make_scripts_executable.sh /path/to/dir  # Specific directory
./scripts/make_scripts_executable.sh . -v          # Verbose mode (shows all files)

# Clean up log files
./scripts/clean_logs.sh

# Clean up commons dist directories
./scripts/clean_commons_dist.sh

# Clean up Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Docker cleanup
docker system prune -a               # Remove unused containers, images, networks
docker volume prune                  # Remove unused volumes
```

### Debugging

```bash
# Navigate to services directory
cd services

# View service configuration
docker-compose config

# Check service health
curl http://localhost:8003/health    # Replace port for different services

# Interactive debugging
cd cart
pipenv run python -m pdb app/main.py

# Connect to running container (from services directory)
cd ..
docker-compose exec cart bash
# Inside container:
ps aux                               # Check processes
netstat -tlnp                        # Check listening ports
env | grep MONGO                     # Check environment variables
```

### Using Dapr (Alternative)

```bash
# Navigate to services directory
cd services

# IMPORTANT: When using Dapr, you need to start MongoDB and Redis separately
# as they are not managed by Dapr

# First, start MongoDB and Redis
docker-compose up -d mongodb redis

# Initialize Dapr (only needed once)
dapr init

# Run all services with Dapr
dapr run -f dapr.yaml

# Run individual service with Dapr
cd cart
dapr run --app-id cart --app-port 8003 --dapr-http-port 3503 \
  --components-path ../dapr/components \
  -- pipenv run uvicorn app.main:app --host 0.0.0.0 --port 8003

# Check Dapr status
dapr list
dapr dashboard  # Opens web UI at http://localhost:8080

# When done, stop MongoDB and Redis (from services directory)
cd ..
docker-compose down mongodb redis
```

### Environment Variables

```bash
# Create local environment file
cp .env.example .env
# Edit .env with your values

# Override for specific service
cd services/cart
cp .env.example .env.local
# .env.local takes precedence over .env

# View current environment (from services directory)
cd ..
docker-compose exec cart env | sort
```

### Troubleshooting

```bash
# Navigate to services directory
cd services

# Service won't start - check logs
docker-compose logs cart | tail -50

# MongoDB connection issues
docker exec -it mongodb mongosh --eval "db.adminCommand('ping')"
../scripts/init-mongodb-replica.sh

# Port conflicts
lsof -i :8003                        # Find process using port
kill -9 $(lsof -t -i :8003)         # Kill process on port

# Reset everything
docker-compose down -v
../scripts/reset-mongodb.sh
docker-compose up -d
```

## High-Level Architecture Patterns

### 1. State Machine Pattern (Cart Service)
The cart service uses a state machine pattern to manage cart lifecycle:
- States: initial → idle → entering_item → paying → completed/cancelled
- State transitions are managed by `cart_state_manager.py`
- Each state inherits from `abstract_state.py`

### 2. Plugin Architecture
Multiple services use plugin systems for extensibility:
- **Cart**: Payment methods (`/services/strategies/payments/`) and sales promotions
- **Report**: Report generators (`/services/plugins/`)
- Plugins are configured via `plugins.json` files

### 3. Multi-Tenancy
- Database isolation: Each tenant has a separate MongoDB database
- API requests include tenant_code in headers
- Terminal authentication uses API keys

### 4. Event-Driven Communication
- Transaction logs are published via Dapr pub/sub topics:
  - `tranlog_report`: Transaction data for reports
  - `tranlog_status`: Transaction status updates
  - `cashlog_report`: Cash in/out events
  - `opencloselog_report`: Terminal open/close events

### 5. Circuit Breaker Pattern
The system implements circuit breaker pattern to handle failures gracefully:

**Implementation Details:**
- **Failure Threshold**: 3 consecutive failures trigger circuit opening
- **Timeout**: 60 seconds before attempting recovery (half-open state)
- **States**: Closed (normal) → Open (failing) → Half-Open (testing)

**Applied to:**
- External HTTP service calls (via `HttpClientHelper`)
- Dapr state store operations (via `DaprClientHelper`)
- Dapr pub/sub event publishing (via `DaprClientHelper`)
- Individual service implementations (`PubsubManager`, `StateStoreManager`)

### 6. Dapr Communication
All Dapr communication is unified through `DaprClientHelper`:

**Features:**
- Unified interface for pub/sub and state store operations
- Built-in circuit breaker pattern
- Automatic retry via `HttpClientHelper`
- Connection pooling and reuse
- Proper error handling and logging

**Usage:**
```python
from kugel_common.utils.dapr_client_helper import get_dapr_client

# Publish event
async with get_dapr_client() as client:
    await client.publish_event("pubsub", "topic", {"data": "value"})

# State operations
async with get_dapr_client() as client:
    await client.save_state("statestore", "key", {"value": "data"})
    data = await client.get_state("statestore", "key")
```

### 7. Shared Commons Library
The `commons` package provides:
- Database abstractions (`AbstractRepository`, `AbstractDocument`)
- Exception handling with structured error codes
- Authentication/security utilities
- API response schemas
- Request logging middleware
- HTTP client helpers (`HttpClientHelper`, `DaprClientHelper`)

## Error Code Structure
Error codes follow XXYYZZ format:
- XX: Service identifier (10=account, 20=terminal, 30=cart, etc.)
- YY: Feature/module identifier
- ZZ: Specific error number

## Database Conventions
- Collections use snake_case naming
- Documents inherit from `BaseDocumentModel`
- Repositories follow the repository pattern
- Async operations throughout using Motor

## API Conventions
- All endpoints are versioned: `/api/v1/`
- Request/response models use Pydantic schemas
- Transformer classes convert between internal models and API schemas
- OpenAPI documentation auto-generated by FastAPI

## Testing Conventions
- Test files follow pattern: `test_*.py`
- Test execution order: `test_clean_data.py` → `test_setup_data.py` → feature tests
- Async tests use `pytest-asyncio`
- Fixtures defined in `conftest.py`

## Important Configuration
- Environment variables are loaded from `.env` files
- Service-specific settings in `/config/settings_*.py`
- Dapr components configured in `/dapr/components/`
- Database connection strings include tenant code in the database name
- Dapr HTTP port: Default 3500 (configurable via `DAPR_HTTP_PORT`)
- Circuit breaker thresholds are configurable per service

## Project Rules and Conventions

### Language Usage
- **Code comments and log messages**: Always in English
- **Primary documentation**: English (README.md, CLAUDE.md, etc.)
- **Japanese documentation**: Supplementary only (README_ja.md etc.)
- **Variable/function names**: English only
- **Error messages**: Support both English and Japanese (using language codes)

### Code Style
- Follow PEP 8 for Python code
- Use type hints for function parameters and return values
- Async/await patterns for all database operations
- No commented-out code in production

### Git Conventions
- Commit messages in English
- Branch naming: feature/*, bugfix/*, hotfix/*
- PR descriptions should explain the "why" not just the "what"

### Security
- Never commit secrets or API keys
- Use environment variables for configuration
- API keys should be hashed when stored
- Implement proper input validation on all endpoints

## Active Technologies
- Python 3.12+ + FastAPI, Motor (MongoDB async driver), Pydantic, pytest-asyncio (001-logical-delete)
- MongoDB（テナント毎にデータベース分離、Motor async driver使用） (001-logical-delete)

## Recent Changes
- 001-logical-delete: Added Python 3.12+ + FastAPI, Motor (MongoDB async driver), Pydantic, pytest-asyncio

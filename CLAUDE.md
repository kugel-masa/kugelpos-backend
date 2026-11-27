# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kugelpos is a microservices-based Point of Sale (POS) backend system built with FastAPI, MongoDB, and Dapr. The system consists of 7 core services that communicate via Dapr service mesh and RabbitMQ pub/sub.

## Architecture

### Core Services
| Service | Port | Description |
|---------|------|-------------|
| account | 8000 | User authentication and JWT token management |
| terminal | 8001 | Terminal/store management and API key handling |
| master-data | 8002 | Product catalog, payment methods, tax rules, staff management |
| cart | 8003 | Shopping cart, transaction processing with state machine pattern |
| report | 8004 | Sales reports and daily summaries with plugin architecture |
| journal | 8005 | Electronic journal and transaction log storage |
| stock | 8006 | Inventory management and stock tracking |

### Key Technologies
- **Python 3.12+** with FastAPI for REST APIs
- **MongoDB** (PyMongo async API) for persistence
- **Redis** for caching and state management
- **RabbitMQ** for pub/sub messaging (via Dapr)
- **Dapr** for service mesh, state management, and pub/sub
- **Docker & Docker Compose** for containerization
- **Pipenv** for dependency management

## Common Development Commands

### Quick Start
```bash
./scripts/build.sh       # Build all services
./scripts/start.sh       # Start all services
./scripts/stop.sh        # Stop all services
```

**Detailed guides:** `/build`, `/service` commands

### Testing
Tests are split into three tiers per service: `tests/unit/` (no external
deps), `tests/integration/` (real MongoDB only, other services mocked),
and `tests/e2e/` (full docker-compose stack). Cross-service e2e scenarios
live in the repo-root `tests/e2e/` directory (own Pipfile-managed venv)
and run automatically after the per-service e2e suites.

```bash
./scripts/run_unit_tests.sh                       # All services, no MongoDB needed
./scripts/run_integration_tests.sh                # All services, MongoDB only
./scripts/run_e2e_tests.sh                        # All services, full stack
./scripts/run_all_tests_with_progress.sh          # Legacy: per-service runner

cd services/cart && pipenv run pytest -m unit     # Single service, single tier
```

Cart's e2e depends on `CART_REQUEST_SNAPSHOT_MODE`. The default `DUAL` runs all
96; under `REQUIRED` the 48 marked `dual_only` are refused by design and have to
be deselected. See `/test-guide`.

**Detailed guides:** `/test-guide` command, `docs/ja/testing-tiers.md`

### Code Quality
```bash
cd services/<service>
pipenv run ruff check app/           # Check
pipenv run ruff check --fix app/     # Auto-fix
pipenv run ruff format app/          # Format
```

## High-Level Architecture Patterns

### 1. State Machine Pattern (Cart Service)
States: initial → idle → entering_item → paying → completed/cancelled
- Managed by `cart_state_manager.py`
- Each state inherits from `abstract_state.py`

### 2. Plugin Architecture
- **Cart**: Payment methods (`/services/strategies/payments/`)
- **Report**: Report generators (`/services/plugins/`)
- Configured via `plugins.json` files

### 3. Multi-Tenancy
- Database isolation: Each tenant has a separate MongoDB database
- API requests include tenant_code in headers
- Terminal authentication uses API keys

### 4. Event-Driven Communication
Dapr pub/sub topics (backed by RabbitMQ):
- `tranlog_report`: Transaction data for reports
- `tranlog_status`: Transaction status updates
- `cashlog_report`: Cash in/out events
- `opencloselog_report`: Terminal open/close events

### 5. Circuit Breaker Pattern
- Failure Threshold: 3 consecutive failures
- Timeout: 60 seconds before recovery
- Applied to: HTTP calls, Dapr state/pub-sub operations

### 6. Shared Commons Library
`kugel_common` package provides:
- Database abstractions (`AbstractRepository`, `AbstractDocument`)
- Exception handling with structured error codes
- Authentication/security utilities
- HTTP client helpers (`HttpClientHelper`, `DaprClientHelper`)
- Cache backend abstractions (`AbstractCacheBackend`, `InMemoryCacheBackend`, `DaprStateCacheBackend`)
- Slack notification utilities

### 7. Master-Data Caching (cart only)
Cart's master-data repositories (Item, Payment, Promotion, Settings) inherit
`AbstractMasterDataRepository[TDoc]` (`services/cart/app/models/repositories/`).
Caching, key construction, TTL, invalidation, and backend-failure fallback
live in the base; subclasses only implement `_fetch_one` / `_fetch_list`.
- Backend: Dapr state store `masterstore` (Redis DB 0, like every state store: the
  components set no DB number). Dapr prefixes each key with the app id, so it shares
  `cart||` with cartstore; the `mdcache:` prefix is what keeps the two apart
- Key format: `mdcache:{tenant}:{store or '_'}:{namespace}:gen{N}:s{shape}:{entry_kind}:{logical_key}`
- Tenant-wide masters declare `is_store_scoped = False` (forces store position to `_`)

## Error Code Structure
Format: XXYYZZ (`kugel_common/exceptions/error_codes.py`, `docs/en/general/error_code_spec.md`)
- XX: Error category (10=general, 20=authentication/authorization, 30=input validation,
  40=business rule, 50=database/repository, 60=external service, 90=system)
- YY: Subcategory. Within business rules (40YYZZ) the services own ranges:
  cart 401–404, master-data 405, terminal 406–407, account 408–409, journal 410–411,
  report 412–413, stock 414–415
- ZZ: Specific error

## Conventions

### Database
- Collections: snake_case
- Documents inherit from `BaseDocumentModel`
- Repository pattern, async operations with the PyMongo async API

### API
- Versioned: `/api/v1/`
- Pydantic schemas for request/response
- Transformer classes for model conversion

### Testing
- Files: `test_*.py`, organized into `tests/unit/`, `tests/integration/`, `tests/e2e/`
- Per-tier conftests auto-mark tests; new tests just need to land in the right directory
- A cart e2e test that does not carry the snapshot needs the `dual_only` mark,
  or it will be read as a REQUIRED-mode failure (#156)
- Test ordering for e2e is enforced via `pytest_collection_modifyitems` (e.g.
  `test_setup_data` runs first), no shell-level ordering required
- Async tests use `pytest-asyncio`

### Code Style
- PEP 8 for Python
- Type hints required
- Async/await for all DB operations
- No commented-out code in production

### Language
- Code/logs/comments: English
- Primary docs: English
- Variable/function names: English only

### Git
- Commit messages: English
- Branches: feature/*, bugfix/*, hotfix/*

### Security
- Never commit secrets
- Use environment variables
- Hash API keys when stored

## Available Commands

| Command | Description |
|---------|-------------|
| `/build` | Build services (all / individual / common package) |
| `/service` | Start / stop / restart services (including Dapr sidecars) |
| `/deploy` | Deployment procedure for Azure Container Apps |
| `/test-guide` | Test execution guide (including Event Loop issue handling) |
| `/db-review` | Review MongoDB aggregation pipelines |

## Important Configuration
- Environment variables loaded from `.env` files
- Service settings in `/config/settings_*.py`
- Dapr components in `/dapr/components/`
- Dapr HTTP port: Default 3500 (configurable via `DAPR_HTTP_PORT`)

## Active Technologies
- Python 3.12+ + FastAPI, Pydantic v2, PyMongo async API, Dapr (through the existing `DaprClientHelper` wrapper) (072-master-data-cache)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, Dapr (state store `cartstore`). Signing uses only the standard library (`hmac` / `hashlib` / `json`) — **no new external dependency** (148-cart-snapshot-restore)
- New `log_cart_restore` collection in the per-tenant MongoDB database (`db_cart_{tenant_id}`). The cart cache (Redis, falling back to `cache_cart`) is unchanged (148-cart-snapshot-restore)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, Dapr (pub/sub `pubsub-tranlog-report` / topic `topic-tranlog`, state store). Signing reuses phase 1's `kugel_common.utils.hmac_signer` (standard library only). Request decompression uses the standard library `gzip`/`zlib` plus the `brotli` package (.NET 8 clients support `br`/`gzip` out of the box) (156-stateless-cart)
- Per-tenant MongoDB databases. The tranlog (report/journal) and stock_update indexes are reworked around `cart_id`. Auditing generalises phase 1's `log_cart_restore` (156-stateless-cart)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, Dapr (master-data cache in `masterstore`). No new external dependency (311-payment-variants)
- Payment variants are embedded in the `master_payment` document (`variants[]`, no index change). Transaction payment lines gain `variant_code` / `builtin_description` (311-payment-variants)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, `HttpClientHelper` (`get_service_client`), PyJWT (the existing service-account token). No new external dependency; the PIN comparison uses the standard library's `secrets` (323-staff-pin-verification)
- `master_staff` and `info_terminal` keep their shape; the staff PIN is compared only inside master-data, behind an internal service-to-service endpoint (323-staff-pin-verification)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, commons' `AbstractRepository`. No new external dependency (324-master-logical-delete)
- Every deletable master (category, item common, item store, item book, payment, promotion, settings, staff) gains an optional `is_deleted`; reads filter `{"is_deleted": {"$ne": True}}` so documents without the field stay visible. Unique indexes unchanged (324-master-logical-delete)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo 4.20 async API (declared `>=4.13`). Motor is removed. No new external dependency: PyMongo was already installed as Motor's dependency (301-pymongo-async-migration)
- Per-tenant MongoDB databases, unchanged: no data format or index change (301-pymongo-async-migration)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, commons' `AbstractRepository`, `insert_if_absent`, `get_service_account_info`, `create_service_token` and `get_service_client`. No new external dependency (343-settlement-snapshot)
- New `settlement_record` (one per terminal session; provisional until its close log reaches report, then final and never rewritten) and `settlement_daily_report` (the frozen daily reports) collections in report's per-tenant database; session-scan indexes on the three log collections; optional settlement fields on the close log (343-settlement-snapshot)
- Python 3.12+ (same as the other services) + FastAPI, Pydantic v2, PyMongo async API, Dapr (pub/sub on RabbitMQ, configuration unchanged: a subscriber gives up after 17 failed deliveries, two short of the sidecar's retry limit, records the event in MongoDB and acknowledges it; `dlq-*` stays as the last resort for events that cannot be recorded), commons' `AbstractRepository` and `slack_notifier`, plus a new `get_user_with_token` that refuses terminal and service-account JWTs. Shared code in the new `kugel_common.dead_letter`. No new external dependency (230-dead-letter-handling)
- New `dead_letter` (one record per subscriber and event: failing, pending, replaying, replayed or discarded) and `dead_letter_alert` collections in report's, journal's and stock's per-tenant databases (230-dead-letter-handling)

## Recent Changes
- 072-master-data-cache: Added Python 3.12+ + FastAPI, Pydantic v2, Motor (async MongoDB), Dapr (through the existing `DaprClientHelper` wrapper)

<!--
Sync Impact Report:
Version: 0.0.0 → 1.0.0
Change Type: MAJOR (Initial constitution creation)
Modified Principles: N/A (Initial version)
Added Sections: All (I-VII principles, Architecture Standards, Testing & Quality, Governance)
Removed Sections: N/A
Templates Requiring Updates:
  ✅ plan-template.md - Constitution Check section ready for principle validation
  ✅ spec-template.md - Aligns with functional requirements and testable scenarios
  ✅ tasks-template.md - Compatible with test-first workflow and user story organization
Follow-up TODOs: None - all placeholders filled
-->

# Kugelpos POS Backend Constitution

## Core Principles

### I. Microservices Architecture (NON-NEGOTIABLE)

The system MUST follow microservices architecture with clear service boundaries:

- **Service Isolation**: Each service (account, terminal, master-data, cart, report, journal, stock) operates independently with its own database
- **Multi-Tenancy**: Database isolation per tenant using separate MongoDB databases named with tenant_code
- **Service Communication**: All inter-service communication MUST use Dapr service mesh or Redis pub/sub
- **API Versioning**: All endpoints MUST use `/api/v1/` versioning prefix

**Rationale**: Service isolation ensures scalability, maintainability, and allows independent deployment of business domains. Multi-tenancy at database level provides data security and tenant isolation.

### II. Test-First Development (NON-NEGOTIABLE)

All code changes MUST follow test-driven development (TDD) workflow:

- **Test Execution Order**: Tests run in sequence: `test_clean_data.py` → `test_setup_data.py` → feature tests
- **Async Testing**: All tests MUST use `pytest-asyncio` for async operations
- **Test Organization**: Test files MUST follow `test_*.py` naming pattern
- **Coverage**: Integration tests required for new features, contract changes, and inter-service communication
- **Verification**: Tests written → User approved → Tests fail → Then implement (Red-Green-Refactor)

**Rationale**: TDD ensures reliability in a distributed system where failures can cascade across services. Given the financial nature of POS transactions, correctness is paramount.

### III. Shared Commons Library

Common functionality MUST be centralized in the `commons` library:

- **Abstractions**: Database operations use `AbstractRepository` and `AbstractDocument`
- **Error Handling**: Structured error codes follow XXYYZZ format (XX=service, YY=module, ZZ=error)
- **HTTP Helpers**: Use `HttpClientHelper` and `DaprClientHelper` for all HTTP and Dapr operations
- **No Duplication**: Code repeated in 2+ services MUST be moved to commons
- **Version Control**: Commons updates require `update_common_and_rebuild.sh` without `--increment-version` unless API changes

**Rationale**: Centralization reduces duplication, ensures consistent error handling, and simplifies maintenance across 7 services.

### IV. Circuit Breaker & Resilience (NON-NEGOTIABLE)

All external communication MUST implement circuit breaker pattern:

- **Failure Threshold**: 3 consecutive failures trigger circuit opening
- **Recovery Timeout**: 60 seconds before attempting recovery (half-open state)
- **States**: Closed (normal) → Open (failing) → Half-Open (testing)
- **Coverage**: Applied to HTTP calls, Dapr state operations, pub/sub publishing
- **Implementation**: Use `HttpClientHelper` or `DaprClientHelper` exclusively

**Rationale**: In a microservices architecture, cascading failures can bring down the entire system. Circuit breakers prevent fault propagation and enable graceful degradation.

### V. Event-Driven Communication

Asynchronous events MUST be used for cross-service data propagation:

- **Pub/Sub Topics**: `tranlog_report`, `tranlog_status`, `cashlog_report`, `opencloselog_report`
- **Event Publishing**: All transaction-related events MUST be published via Dapr pub/sub
- **Idempotency**: Event handlers MUST be idempotent to handle duplicate deliveries
- **Event Schema**: Events MUST include tenant_code, timestamp, and event_type

**Rationale**: Event-driven architecture decouples services and enables eventual consistency, critical for report generation and audit logs.

### VI. Plugin Architecture for Extensibility

Services MUST use plugin systems for configurable behaviors:

- **Payment Methods**: Cart service payment strategies in `/services/strategies/payments/`
- **Report Generators**: Report service plugins in `/services/plugins/`
- **Plugin Configuration**: Plugins configured via `plugins.json` files
- **Dynamic Loading**: Plugins loaded at runtime without code changes

**Rationale**: Retail environments require flexible payment methods and report formats. Plugin architecture allows customization without core code changes.

### VII. Observability & Debugging

All services MUST implement comprehensive logging and monitoring:

- **Structured Logging**: Use consistent log formats with context (tenant_code, request_id, service_name)
- **Request Logging**: Middleware logs all API requests with timing and status
- **Error Logging**: All exceptions logged with full stack traces and context
- **Health Endpoints**: Each service exposes `/health` endpoint for monitoring
- **Log Language**: All log messages and code comments MUST be in English

**Rationale**: Distributed systems require centralized logging for debugging. Multi-tenancy demands tenant-aware logging for issue isolation.

## Architecture Standards

### Database Conventions

- **Collections**: Use snake_case naming (e.g., `transaction_logs`, `product_masters`)
- **Documents**: All documents MUST inherit from `BaseDocumentModel`
- **Repository Pattern**: All database access MUST use repository pattern via `AbstractRepository`
- **Async Operations**: All database operations MUST use Motor async driver with async/await
- **Connection Strings**: MUST include tenant code in database name and `?replicaSet=rs0`

### API Conventions

- **Request/Response Models**: Use Pydantic schemas exclusively
- **Transformers**: Convert between internal models and API schemas via transformer classes
- **OpenAPI Documentation**: FastAPI auto-generated docs MUST be available at `/docs`
- **Authentication**: Use JWT tokens from account service; API keys for terminal authentication
- **Input Validation**: All endpoints MUST validate inputs via Pydantic models

### State Machine Pattern (Cart Service)

- **States**: initial → idle → entering_item → paying → completed/cancelled
- **State Management**: Transitions managed by `cart_state_manager.py`
- **State Classes**: Each state MUST inherit from `abstract_state.py`
- **No State Leaks**: State transitions MUST be explicit and logged

## Testing & Quality

### Test Requirements

- **Unit Tests**: Required for business logic and calculations
- **Integration Tests**: Required for database operations, state transitions, and plugin interactions
- **Contract Tests**: Required for API endpoint changes and event schema changes
- **Fixtures**: Common test data MUST be defined in `conftest.py`

### Code Quality Standards

- **PEP 8 Compliance**: All Python code MUST follow PEP 8 style guide
- **Type Hints**: Function parameters and return values MUST have type hints
- **Linting**: Use `ruff check` and `ruff format` for linting and formatting
- **No Dead Code**: No commented-out code allowed in production branches
- **Documentation**: Docstrings required for public APIs and complex business logic

### Build & Test Workflow

After code changes, the following sequence MUST be executed:

1. `./scripts/update_common_and_rebuild.sh` (if commons updated)
2. `./scripts/build.sh [service]` (rebuild affected services)
3. `./scripts/stop.sh` (stop running services)
4. `./scripts/start.sh` (start all services with health check)
5. `./run_all_tests.sh` (verify changes)

## Governance

### Constitution Authority

- This constitution supersedes all other development practices and guidelines
- All code reviews MUST verify compliance with principles I-VII
- Violations of NON-NEGOTIABLE principles require constitution amendment before implementation
- Complexity not justified by constitution principles MUST be simplified

### Amendment Process

- **Proposal**: Document proposed change with rationale and impact analysis
- **Review**: Requires approval from project maintainers
- **Migration**: Breaking changes require migration plan for existing code
- **Versioning**: Constitution follows semantic versioning (MAJOR.MINOR.PATCH)
  - MAJOR: Backward incompatible principle removals or redefinitions
  - MINOR: New principle/section added or materially expanded guidance
  - PATCH: Clarifications, wording, typo fixes

### Language Policy

- **Code & Logs**: English only for code comments, log messages, variable/function names
- **Documentation**: Primary documentation in English (README.md, CLAUDE.md)
- **Error Messages**: Support both English and Japanese via language codes
- **Git**: Commit messages in English; branch naming: `feature/*`, `bugfix/*`, `hotfix/*`

### Compliance & Review

- Pull requests MUST verify:
  - Test-first workflow followed (tests written before implementation)
  - Circuit breaker pattern used for external calls
  - Commons library used for shared functionality
  - Event publishing for cross-service communication
  - Structured logging with tenant context
- Security review required for:
  - Authentication/authorization changes
  - API key handling modifications
  - Database access pattern changes
  - Environment variable additions

### Runtime Guidance

For day-to-day development workflow, consult `CLAUDE.md` for:
- Common development commands
- Service management procedures
- Testing and debugging workflows
- Troubleshooting guides

**Version**: 1.0.0 | **Ratified**: 2025-11-29 | **Last Amended**: 2025-11-29

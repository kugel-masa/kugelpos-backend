# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kugelpos is a microservices-based Point of Sale (POS) backend system built with FastAPI, MongoDB, and Dapr. The system consists of 7 core services that communicate via Dapr service mesh and Redis pub/sub.

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
- **MongoDB** (Motor async driver) for persistence
- **Redis** for caching and pub/sub messaging
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
```bash
./scripts/run_all_tests_with_progress.sh      # All services
cd services/cart && pipenv run pytest tests/ -v   # Single service
```

**Detailed guide:** `/test-guide` command

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
Dapr pub/sub topics:
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
- Slack notification utilities

## Error Code Structure
Format: XXYYZZ
- XX: Service (10=account, 20=terminal, 30=cart, 40=master-data, 50=report, 60=journal, 70=stock)
- YY: Feature/module
- ZZ: Specific error

## Conventions

### Database
- Collections: snake_case
- Documents inherit from `BaseDocumentModel`
- Repository pattern, async operations with Motor

### API
- Versioned: `/api/v1/`
- Pydantic schemas for request/response
- Transformer classes for model conversion

### Testing
- Files: `test_*.py`
- Order: `test_clean_data.py` → `test_setup_data.py` → feature tests
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
| `/build` | サービスのビルド（全体/個別/共通パッケージ） |
| `/service` | サービスの起動・停止・再起動（Daprサイドカー含む） |
| `/deploy` | Azure Container Appsへのデプロイ手順 |
| `/test-guide` | テスト実行ガイド（Event Loop問題対処含む） |
| `/db-review` | MongoDB aggregation pipelineのレビュー |

## Important Configuration
- Environment variables loaded from `.env` files
- Service settings in `/config/settings_*.py`
- Dapr components in `/dapr/components/`
- Dapr HTTP port: Default 3500 (configurable via `DAPR_HTTP_PORT`)

# Kugelpos Project Overview

## Purpose
Kugelpos is a microservices-based Point of Sale (POS) backend system designed for retail operations in Japan.

## Tech Stack
- **Language**: Python 3.12+
- **Web Framework**: FastAPI
- **Database**: MongoDB (Motor async driver)
- **Cache/Pub-Sub**: Redis
- **Service Mesh**: Dapr
- **Containerization**: Docker & Docker Compose
- **Dependency Management**: Pipenv
- **Cloud Deployment**: Azure Container Apps

## Core Services (7 services)
| Service | Port | Description |
|---------|------|-------------|
| account | 8000 | User authentication, JWT token management |
| terminal | 8001 | Terminal/store management, API key handling |
| master-data | 8002 | Product catalog, payment methods, tax rules, staff |
| cart | 8003 | Shopping cart, transaction processing (state machine) |
| report | 8004 | Sales reports, daily summaries (plugin architecture) |
| journal | 8005 | Electronic journal, transaction log storage |
| stock | 8006 | Inventory management, stock tracking |

## Architecture Patterns
1. **State Machine Pattern** - Cart service uses states: initial → idle → entering_item → paying → completed/cancelled
2. **Plugin Architecture** - Payment methods, report generators are pluggable
3. **Multi-Tenancy** - Database isolation per tenant, tenant_code in headers
4. **Event-Driven** - Transaction logs via Dapr pub/sub topics
5. **Circuit Breaker** - Failure threshold: 3, timeout: 60s

## Key Directories
- `/services/` - All microservices
- `/services/commons/` - Shared library (kugel_common)
- `/scripts/` - Build, test, deployment scripts
- `/services/dapr/` - Dapr configuration files

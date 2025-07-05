# Kugelpos Documentation Index

English documentation index for the Kugelpos POS system, organized by category.

## 📋 Table of Contents

- [General Documentation](#general-documentation)
- [Common Functions](#common-functions)
- [Service Documentation](#service-documentation)
  - [Account Service](#account-service)
  - [Cart Service](#cart-service)
  - [Journal Service](#journal-service)
  - [Master Data Service](#master-data-service)
  - [Report Service](#report-service)
  - [Stock Service](#stock-service)
  - [Terminal Service](#terminal-service)

---

## General Documentation

Documentation about the overall system architecture and design.

- [**Architecture Specification**](general/architecture.md) - System architecture overview
- [**Configuration Priority**](general/configuration-priority.md) - Environment variables and configuration file priorities
- [**Design Patterns**](general/design-patterns.md) - Design patterns used in the system
- [**Error Code Specification**](general/error_code_spec.md) - Error code system and list
- [**Frontend Guide**](general/frontend_guide.md) - Guide for frontend developers
- [**HTTP Communication**](general/http-communication.md) - Inter-service HTTP communication conventions

## Common Functions

Documentation for functionality shared across all services.

- [**Common Function Specification**](commons/common-function-spec.md) - Detailed specification of the kugel_common library

## Service Documentation

API specifications and data model specifications for each microservice.

### Account Service

Service providing user authentication and JWT token management.

- [**API Specification**](account/api-specification.md) - REST API endpoint specification
- [**Model Specification**](account/model-specification.md) - Data models and database structure

### Cart Service

Service managing shopping carts and transaction processing.

- [**API Specification**](cart/api-specification.md) - REST API endpoint specification
- [**Model Specification**](cart/model-specification.md) - Data models and state machine specification

### Journal Service

Service providing electronic journal management functionality.

- [**API Specification**](journal/api-specification.md) - REST API endpoint specification
- [**Model Specification**](journal/model-specification.md) - Data models and event processing specification

### Master Data Service

Service managing master data such as products, stores, and payment methods.

- [**API Specification**](master-data/api-specification.md) - REST API endpoint specification
- [**Model Specification**](master-data/model-specification.md) - Various master data model specifications

### Report Service

Service providing various report generation functionality.

- [**API Specification**](report/api-specification.md) - REST API endpoint specification
- [**Model Specification**](report/model-specification.md) - Report data model specification

### Stock Service

Service providing inventory management functionality.

- [**API Specification**](stock/api-specification.md) - REST API endpoint specification
- [**Model Specification**](stock/model-specification.md) - Inventory data model specification
- [**Snapshot Specification**](stock/snapshot-specification.md) - Inventory snapshot functionality specification
- [**WebSocket Specification**](stock/websocket-specification.md) - WebSocket specification for real-time inventory updates

### Terminal Service

Service providing terminal management and API key authentication.

- [**API Specification**](terminal/api-specification.md) - REST API endpoint specification
- [**Model Specification**](terminal/model-specification.md) - Terminal data model specification

---

## 📝 Additional Information

### Documentation Conventions

- **API Specification**: Describes REST endpoints, request/response formats, and authentication methods for each service
- **Model Specification**: Describes database schemas, data model definitions, and business logic
- **File Naming**: All lowercase with hyphen separation (kebab-case)

### Related Links

- [Japanese Documentation](../ja/README.md)
- [Project Root](../../README.md)
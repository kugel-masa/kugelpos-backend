# Dapr Components Documentation

This document describes the Dapr components used in the Kugelpos microservices architecture and which services actively utilize each component.

## Overview

Kugelpos uses Dapr (Distributed Application Runtime) for:
- **State Management**: Redis-based state stores for caching and state persistence
- **Pub/Sub Messaging**: Redis-based pub/sub for event-driven communication between services
- **Service Mesh**: Service-to-service communication and discovery

## Components Directory Structure

```
/services/dapr/components/
├── cartstore.yaml              # State store for cart service
├── pubsub_cashlog_report.yaml  # Pub/sub for cash in/out events
├── pubsub_opencloselog_report.yaml  # Pub/sub for terminal open/close events
├── pubsub_tranlog_report.yaml  # Pub/sub for transaction logs
├── statestore.yaml             # Generic state store for event deduplication
└── terminalstore.yaml          # State store (unused - configured but not used by any service)
```

## Active State Store Components

### 1. Generic State Store (`statestore.yaml`)
- **Type**: `state.redis`
- **Redis DB Index**: 1
- **TTL**: 1 hour (3600 seconds)
- **Used by**: `report`, `journal`, and `stock` services
- **Purpose**: 
  - Idempotent message processing - tracking processed event IDs
  - Preventing duplicate processing of pub/sub messages
  - Simple key-value storage for event deduplication

```yaml
metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "3600"
  - name: databaseIndex
    value: "1"
```

### 2. Cart Store (`cartstore.yaml`)
- **Type**: `state.redis`
- **Redis DB Index**: 2
- **TTL**: 10 hours (36000 seconds)
- **Used by**: `cart` service
- **Purpose**: 
  - Caching cart documents during transactions
  - Implementing circuit breaker pattern with MongoDB fallback
  - Storing cart state during the transaction lifecycle

```yaml
metadata:
  - name: redisHost
    value: redis:6379
  - name: ttlInSeconds
    value: "36000"
  - name: databaseIndex
    value: "2"
```

## Pub/Sub Components

### 1. Transaction Log Pub/Sub (`pubsub_tranlog_report.yaml`)
- **Type**: `pubsub.redis`
- **Stream Name**: `topic-tranlog`
- **Processing Timeout**: 180 seconds
- **Publishers**: `cart` service
- **Subscribers**: 
  - `report` service (route: `/api/v1/tranlog`)
  - `journal` service (route: `/api/v1/tranlog`)
  - `stock` service (route: `/api/v1/tranlog`)
- **Purpose**: Distributes transaction logs from cart service to reporting, journaling, and stock services

### 2. Cash Log Pub/Sub (`pubsub_cashlog_report.yaml`)
- **Type**: `pubsub.redis`
- **Stream Name**: `topic-cashlog`
- **Processing Timeout**: 180 seconds
- **Publishers**: `terminal` service
- **Subscribers**:
  - `report` service (route: `/api/v1/cashlog`)
  - `journal` service (route: `/api/v1/cashlog`)
- **Purpose**: Distributes cash in/out events from terminal service to reporting and journaling services

### 3. Open/Close Log Pub/Sub (`pubsub_opencloselog_report.yaml`)
- **Type**: `pubsub.redis`
- **Stream Name**: `topic-opencloselog`
- **Processing Timeout**: 180 seconds
- **Publishers**: `terminal` service
- **Subscribers**:
  - `report` service (route: `/api/v1/opencloselog`)
  - `journal` service (route: `/api/v1/opencloselog`)
- **Purpose**: Distributes terminal open/close events from terminal service to reporting and journaling services

## Service Component Usage Matrix

| Service | State Stores | Pub/Sub (Publisher) | Pub/Sub (Subscriber) |
|---------|--------------|---------------------|---------------------|
| **terminal** | - | pubsub-cashlog-report<br>pubsub-opencloselog-report | - |
| **cart** | cartstore | pubsub-tranlog-report | - |
| **report** | statestore | - | pubsub-tranlog-report<br>pubsub-cashlog-report<br>pubsub-opencloselog-report |
| **journal** | statestore | - | pubsub-tranlog-report<br>pubsub-cashlog-report<br>pubsub-opencloselog-report |
| **stock** | statestore | - | pubsub-tranlog-report |

## Component Usage Details by Service

### Terminal Service
- **Role**: Event publisher
- **Pub/Sub Publishers**:
  - `pubsub-cashlog-report`: Publishes cash in/out events
  - `pubsub-opencloselog-report`: Publishes terminal open/close events
- **Primary Storage**: MongoDB for terminal data

### Cart Service
- **Role**: State management and event publishing
- **State Store**:
  - `cartstore` for caching cart documents during transactions
- **Pub/Sub Publishers**:
  - `pubsub-tranlog-report`: Publishes completed transaction logs
- **Implementation**: Uses direct HTTP calls to Dapr state API (legacy pattern)
- **Primary Storage**: MongoDB for permanent storage, Redis for caching

### Report Service
- **Role**: Event consumer with idempotent processing
- **State Store**:
  - `statestore` for tracking processed event IDs (idempotency)
  - Prevents duplicate processing of pub/sub messages
  - Circuit breaker pattern for resilience
- **Pub/Sub Subscribers**:
  - `pubsub-tranlog-report`: Receives transaction logs
  - `pubsub-cashlog-report`: Receives cash movement logs
  - `pubsub-opencloselog-report`: Receives terminal open/close logs
- **Primary Storage**: MongoDB for aggregated reports

### Journal Service
- **Role**: Event consumer with idempotent processing
- **State Store**:
  - `statestore` for tracking processed event IDs (idempotency)
  - Prevents duplicate processing of pub/sub messages
  - Circuit breaker pattern for resilience
- **Pub/Sub Subscribers**:
  - `pubsub-tranlog-report`: Receives transaction logs
  - `pubsub-cashlog-report`: Receives cash movement logs
  - `pubsub-opencloselog-report`: Receives terminal open/close logs
- **Primary Storage**: MongoDB for electronic journal entries

### Stock Service
- **Role**: Event consumer with idempotent processing
- **State Store**:
  - `statestore` for tracking processed event IDs (idempotency)
  - Prevents duplicate processing of pub/sub messages
  - Circuit breaker pattern for resilience
- **Pub/Sub Subscribers**:
  - `pubsub-tranlog-report`: Receives transaction logs for stock updates
- **Primary Storage**: MongoDB for stock data
- **WebSocket Features**: Stock alerts and reorder point notifications work independently of Dapr

## Architecture Patterns

### 1. Event-Driven Architecture
- **Producers**: `cart` and `terminal` services generate business events
- **Consumers**: `report`, `journal`, and `stock` services process events asynchronously
- **Benefits**: Loose coupling, scalability, fault tolerance

### 2. Circuit Breaker Pattern
- **Implementation**: 
  - Cart service with `cartstore` for caching
  - Report/Journal/Stock services with `statestore` for idempotency
- **Behavior**: Automatically falls back or continues processing if state store is unavailable
- **Benefits**: Resilience, graceful degradation

### 3. Fan-out Messaging
- **Pattern**: One publisher, multiple subscribers
- **Example**: Transaction logs published once, consumed by both report and journal
- **Benefits**: Efficient event distribution, independent scaling

### 4. State Store Isolation
- **Design**: Each service has its own Redis database index
- **Benefits**: Data isolation, independent TTL management, no key conflicts

### 5. Idempotent Message Processing
- **Implementation**: Report, journal, and stock services track processed event IDs
- **Mechanism**: Check state store before processing, save event ID after success
- **Benefits**: Exactly-once processing semantics, resilience to retries

## Configuration Notes

1. **Redis Connection**: All components use `redis:6379` (Docker Compose service name)
2. **Processing Timeout**: All pub/sub components use 180-second timeout
3. **TTL Configuration**: 
   - Generic state store: 1 hour (for event deduplication)
   - Cart store: 10 hours (long-lived for active sessions)
4. **Actor Support**: All state stores have `actorStateStore: false` (not using Dapr actors)

## Event Flow Diagram

```
┌─────────────┐                     ┌─────────────┐
│   Terminal  │                     │    Cart     │
│   Service   │                     │   Service   │
└─────┬───────┘                     └─────┬───────┘
      │                                   │
      │ publishes                         │ publishes
      ├─► pubsub-cashlog-report          │
      │                                   │
      └─► pubsub-opencloselog-report     └─► pubsub-tranlog-report
           │                                   │
           │                                   │
           ├──────────────┬────────────────────┤
           │              │                    │
           ▼              ▼                    ▼
    ┌─────────────┐ ┌─────────────┐    ┌─────────────┐
    │   Report    │ │   Report    │    │   Report    │
    │  Service    │ │  Service    │    │  Service    │
    └─────────────┘ └─────────────┘    └─────────────┘
           │              │                    │
           ▼              ▼                    ▼
    ┌─────────────┐ ┌─────────────┐    ┌─────────────┐
    │   Journal   │ │   Journal   │    │   Journal   │
    │  Service    │ │  Service    │    │  Service    │
    └─────────────┘ └─────────────┘    └─────────────┘
```

## Implementation Notes

1. **Unused Component**: `terminalstore.yaml` is configured but not used by any service
2. **Cart Service Pattern**: Uses legacy direct HTTP calls to Dapr state API instead of `DaprClientHelper`
3. **Stock WebSocket Features**: Real-time stock alerts work independently without additional Dapr components
4. **Database Indices**: cartstore(2), statestore(1), terminalstore(3) for isolation
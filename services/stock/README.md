# Stock Service

The Stock Service manages inventory and stock levels for the Kugelpos POS system.

## Overview

This microservice provides:
- Real-time stock tracking
- Stock update history
- Stock snapshots
- Integration with transaction processing via Dapr pub/sub

## Key Features

- **Stock Management**: Track current quantities and minimum thresholds
- **Update History**: Full audit trail of all stock changes
- **Snapshots**: Periodic stock level captures for reporting
- **Transaction Integration**: Automatic stock updates from sales transactions
- **Multi-tenancy**: Isolated data per tenant

## API Endpoints

### Stock Operations
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}` - Get stock info
- `PUT /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/update` - Update stock
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/history` - Get history
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock` - List all stock
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/low` - Get low stock items
- `PUT /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/{item_code}/minimum` - Set minimum

### Snapshot Operations
- `POST /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot` - Create snapshot
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot` - List snapshots
- `GET /api/v1/tenants/{tenant_id}/stores/{store_code}/stock/snapshot/{snapshot_id}` - Get snapshot

### Tenant Management
- `POST /api/v1/tenants` - Setup tenant database

## Configuration

- Internal Port (Docker): 8000
- External Port (localhost): 8006

## Pub/Sub Integration

Subscribes to:
- `tranlog_report` - Receives transaction events from cart service

## Testing

Run tests with:
```bash
./run_all_tests.sh
```
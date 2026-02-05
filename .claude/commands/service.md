---
description: Start, stop, or restart services (including Dapr sidecars)
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/service <ACTION> [SERVICES...] [OPTIONS]`

**Examples:**
- `/service start` → Start all services
- `/service stop` → Stop all services
- `/service restart cart report` → Restart cart and report (with Dapr sidecars)
- `/service stop --clean` → Stop + delete data
- `/service logs cart` → Show logs

## Actions

| Action | Description |
|--------|-------------|
| `start` | Start services (includes MongoDB replica set initialization) |
| `stop` | Stop services |
| `restart` | Restart services (with Dapr sidecars) |
| `status` | Check service status |
| `logs` | Show logs |

## Service & Dapr Sidecar Mapping

**Important:** When restarting specific services, Dapr sidecars must also be restarted

| Service | Dapr Sidecar | Port |
|---------|--------------|------|
| account | dapr_account | 8000 |
| terminal | dapr_terminal | 8001 |
| master-data | dapr_master_data | 8002 |
| cart | dapr_cart | 8003 |
| report | dapr_report | 8004 |
| journal | dapr_journal | 8005 |
| stock | dapr_stock | 8006 |

## Commands

### Start All Services
```bash
./scripts/start.sh
```

### Stop All Services
```bash
./scripts/stop.sh
```

### Stop + Delete Data
```bash
./scripts/stop.sh --clean
```

### Restart Specific Services (with Dapr Sidecars)
```bash
# Restart cart
cd services && docker-compose restart cart dapr_cart

# Restart multiple services
cd services && docker-compose restart cart dapr_cart report dapr_report

# Restart master-data (note the underscore)
cd services && docker-compose restart master-data dapr_master_data
```

### Start Specific Services Only
```bash
cd services && docker-compose up -d cart dapr_cart
```

### Stop Specific Services Only
```bash
cd services && docker-compose stop cart dapr_cart
```

### Check Service Status
```bash
cd services && docker-compose ps
```

### Show Logs
```bash
# All services
cd services && docker-compose logs -f

# Specific service + Dapr
cd services && docker-compose logs -f cart dapr_cart

# Last 100 lines
cd services && docker-compose logs --tail=100 cart dapr_cart
```

## Typical Workflows

### Start Development
```bash
./scripts/start.sh
```

### End Development
```bash
./scripts/stop.sh
```

### After Code Changes (Specific Service)
```bash
# Build → Restart (with Dapr)
cd scripts && ./build.sh cart
cd services && docker-compose restart cart dapr_cart
```

### On Issues (Clean Restart)
```bash
./scripts/stop.sh --clean
./scripts/start.sh
```

### Debugging
```bash
cd services
docker-compose restart cart dapr_cart && docker-compose logs -f cart dapr_cart
```

## Quick Reference

```bash
# Common commands
./scripts/start.sh                                    # Start all
./scripts/stop.sh                                     # Stop all
cd services && docker-compose restart cart dapr_cart  # Restart cart
cd services && docker-compose logs -f cart            # Watch logs
cd services && docker-compose ps                      # Check status
```

## Service URLs (Local)

| Service | Docs | Health |
|---------|------|--------|
| account | http://localhost:8000/docs | http://localhost:8000/health |
| terminal | http://localhost:8001/docs | http://localhost:8001/health |
| master-data | http://localhost:8002/docs | http://localhost:8002/health |
| cart | http://localhost:8003/docs | http://localhost:8003/health |
| report | http://localhost:8004/docs | http://localhost:8004/health |
| journal | http://localhost:8005/docs | http://localhost:8005/health |
| stock | http://localhost:8006/docs | http://localhost:8006/health |

## Troubleshooting

### MongoDB Connection Error
```bash
./scripts/init-mongodb-replica.sh
```

### Port Conflict
```bash
lsof -i :8003
kill -9 $(lsof -t -i :8003)
```

### Full Reset
```bash
./scripts/stop.sh --clean
./scripts/reset-mongodb.sh
./scripts/start.sh
```

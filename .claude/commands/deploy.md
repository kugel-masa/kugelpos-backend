---
description: Deploy to Azure Container Apps
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/deploy <VERSION> [--env <ENVIRONMENT>]`

- `VERSION`: Version tag to deploy (e.g., v0.2.1)
- `--env`: Environment (dev/staging/prod) - Default: dev

**Examples:**
- `/deploy v0.2.1` → Deploy to dev environment
- `/deploy v0.2.1 --env staging` → Deploy to staging environment
- `/deploy v0.2.1 --env prod` → Deploy to production environment

## Environment Configuration

Configure the following variables per environment:

| Environment | DOMAIN | RESOURCE_GROUP | STATUS |
|-------------|--------|----------------|--------|
| dev | `<your-app-name>.japaneast.azurecontainerapps.io` | `<your-resource-group>` | Configure in .env |
| staging | (TBD) | (TBD) | Not configured |
| prod | (TBD) | (TBD) | Not configured |

**Note:** staging/prod environments will be added later. Using them will return an error.

## Release Steps

### Step 1: Pre-Release Verification

Before deploying, verify:
- [ ] All tests passing: `./scripts/run_all_tests_with_progress.sh`
- [ ] Git tag created and pushed
- [ ] Current branch is clean (`git status`)

### Step 2: Build & Push Docker Images (~35-40 minutes)

```bash
echo "y" | ./scripts/build-and-push-azure.sh -t <VERSION> --push
```

**What it does:**
- Builds Docker images for all 7 services
- Tags: `<VERSION>` and `latest`
- Platform: `linux/amd64`
- Automatically pushes to Azure Container Registry

### Step 3: Update Azure Container Apps (~2-5 minutes)

**Option A: All services at once**
```bash
echo "y" | ./scripts/update-azure-container-apps.sh -t <VERSION>
```

**Option B: Staged rollout (recommended)**
```bash
# 1. Update report service first
echo "y" | ./scripts/update-azure-container-apps.sh -t <VERSION> -s "report"

# 2. Verify report is healthy, then update remaining services
echo "y" | ./scripts/update-azure-container-apps.sh -t <VERSION> -s "account,terminal,master-data,cart,journal,stock"
```

### Step 4: Health Check

```bash
./scripts/check_service_health.sh -a <DOMAIN> -v
```

**Expected output:**
```
=== Service Health Check ===
✓ account: HEALTHY
✓ terminal: HEALTHY
✓ master-data: HEALTHY
✓ cart: HEALTHY
✓ report: HEALTHY
✓ journal: HEALTHY
✓ stock: HEALTHY

All services are healthy!
```

### Rollback Procedure

If issues are detected:
```bash
echo "y" | ./scripts/update-azure-container-apps.sh -t <PREVIOUS_VERSION>
```

## Target Services (7 services)

| Service | Endpoint Pattern |
|---------|------------------|
| account | https://account.<DOMAIN>/health |
| terminal | https://terminal.<DOMAIN>/health |
| master-data | https://master-data.<DOMAIN>/health |
| cart | https://cart.<DOMAIN>/health |
| report | https://report.<DOMAIN>/health |
| journal | https://journal.<DOMAIN>/health |
| stock | https://stock.<DOMAIN>/health |

**Note:** Redis is excluded (uses Docker image directly)

## Post-Release Checklist

- [ ] All services showing "HEALTHY" status
- [ ] All components (MongoDB, Dapr) operational
- [ ] Monitor logs for any errors in first 10 minutes
- [ ] Test critical user flows

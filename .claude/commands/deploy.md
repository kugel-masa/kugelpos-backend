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

## Required Secrets and Settings

Startup refuses empty or published values, so a container app missing one of
these does not come up (it fails its health check rather than running open).

| Variable | Services | Value |
|----------|----------|-------|
| `SECRET_KEY` | all 7 | A secret of your own, the **same** in every service (issue #132) |
| `PUBSUB_NOTIFY_API_KEY` | all 7 | A secret of your own, the **same** in every service (issue #132) |
| `APP_API_TOKEN` | report, journal, stock | **Do not set it.** Container Apps injects it (see below) (issue #134) |

- Never set `ALLOW_INSECURE_DEV_SECRETS`: it exists for the development compose
  stack and the tests only, and lets a service start on the published values.
- Generate a secret with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`
  and store it as a Container Apps secret referenced by the environment
  variable, not as a plain value.
- Changing `SECRET_KEY` invalidates every token already issued: users and
  terminals have to sign in again. Do it in a window where that is acceptable.

### APP_API_TOKEN on Container Apps

report, journal and stock accept a pub/sub delivery only if it carries the
`dapr-api-token` header matching their `APP_API_TOKEN`. With Dapr enabled,
Container Apps generates that token per app and revision, injects it into the
app container as `APP_API_TOKEN`, and its managed sidecar sends it on every
delivery ([Microsoft Learn](https://learn.microsoft.com/azure/container-apps/dapr-authentication-token)).
So:

- Dapr must be enabled on report, journal and stock (it already is for pub/sub).
- Do not add `APP_API_TOKEN` to their environment yourself. A value of your own
  would differ from the one the sidecar sends, and every delivery would be
  refused with a 401.
- The token can change between revisions; the services read it at startup, so
  a new revision picks up the new one.

## Release Steps

### Step 1: Pre-Release Verification

Before deploying, verify:
- [ ] All tests passing: `./scripts/run_all_tests_with_progress.sh`
- [ ] Git tag created and pushed
- [ ] Current branch is clean (`git status`)
- [ ] `SECRET_KEY` and `PUBSUB_NOTIFY_API_KEY` are set, as secrets of your own,
      to the same values on all 7 container apps (see Required Secrets and Settings)
- [ ] `APP_API_TOKEN` and `ALLOW_INSECURE_DEV_SECRETS` are **not** set on any
      container app
- [ ] Dapr is enabled on report, journal and stock

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
- [ ] A service that is not HEALTHY: check its log for a settings error naming
      `SECRET_KEY`, `PUBSUB_NOTIFY_API_KEY` or `APP_API_TOKEN` (empty, or a
      published value)
- [ ] After a test sale, report, journal and stock received it: the sale shows
      in the report and the journal, and no `Refused a request to /api/v1/...`
      warning appears in their logs. That warning on every delivery means the
      sidecar and the app disagree on `APP_API_TOKEN`; the events are retried
      and then kept in the dead-letter queue, not lost
- [ ] Test critical user flows

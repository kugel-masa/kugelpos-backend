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
| `TENANT_PROVISIONING_KEY` | account | A secret of your own, held only by whoever onboards tenants: `POST /api/v1/accounts/register` requires it in `X-Provisioning-Key` (issue #138) |
| `BASE_URL_REPORT` | terminal | report's API base URL (`http://<report-app>/api/v1`). From #343 every close asks report to confirm the settlement; without it the default `localhost:8004` is used and every close answers 503 / `406016` |

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

### Pub/sub redelivery and dead letters (#230)

Container Apps ignores `services/dapr/components/pubsub-resiliency.yaml`: the
retries are a resiliency policy on each Dapr component of the environment.
report, journal and stock give up on an event's 17th failure and record it as a
dead letter, so the sidecar must deliver at least 19 times; with fewer retries
every failing event goes to `dlq-*` instead, where nobody sees it.

```bash
./scripts/azure-pubsub-resiliency.sh -g <RESOURCE_GROUP> -e <ENVIRONMENT>           # check
./scripts/azure-pubsub-resiliency.sh -g <RESOURCE_GROUP> -e <ENVIRONMENT> --apply   # set what differs
```

The script reads the budget from `pubsub-resiliency.yaml`, sets it on
`pubsub-tranlog-report`, `pubsub-cashlog-report` and `pubsub-opencloselog-report`,
and checks their `requeueInFailure: "false"` and `enableDeadLetter: "true"`
(it reports those, it does not change the components). It exits 1 when
something does not match.

- Set `SLACK_WEBHOOK_URL` on report, journal and stock from Key Vault (below),
  or dead letters are recorded but nobody is notified (each service logs a
  warning at startup).
- Leave the `DEAD_LETTER_*` variables unset: the defaults match the budget.

### Slack webhook from Key Vault (#230)

The incoming webhook URL decides which Slack channel the notices reach; use one
webhook per environment (the development channel for dev). It is a secret: keep
it in Key Vault, never in this repository or in a script.

```bash
# Once per environment, or to change the channel / rotate the URL
az keyvault secret set --vault-name <VAULT> --name slack-webhook-url --value '<WEBHOOK_URL>' -o none

# Every deploy: check; --apply sets what differs
./scripts/azure-slack-webhook.sh -g <RESOURCE_GROUP> \
  --secret-uri https://<VAULT>.vault.azure.net/secrets/slack-webhook-url \
  --apps "<REPORT_APP> <JOURNAL_APP> <STOCK_APP>"
```

For each app the script gives it a managed identity (system-assigned, or the
user-assigned one passed with `--identity <resource-id>`), lets the identity read
the vault's secrets, and sets the secret `slack-webhook-url` as a Key Vault
reference and `SLACK_WEBHOOK_URL=secretref:slack-webhook-url`. `--apply` needs
rights to assign roles (or set access policies) on the vault; a role just
assigned can take a few minutes, so if setting the secret fails right after,
run it again. With the versionless URI above, a new version of the Key Vault
secret reaches the apps without running the script again (within about 30
minutes, or at once with a new revision).
- If a dead-letter notice says the retries ran out before the subscriber gave
  up, and it keeps happening, the environment's retries are too few: run the
  script again.

## Release Steps

### Step 1: Pre-Release Verification

Before deploying, verify:
- [ ] All tests passing: `./scripts/run_all_tests_with_progress.sh`
- [ ] Git tag created and pushed
- [ ] Current branch is clean (`git status`)
- [ ] `SECRET_KEY` and `PUBSUB_NOTIFY_API_KEY` are set, as secrets of your own,
      to the same values on all 7 container apps (see Required Secrets and Settings)
- [ ] `TENANT_PROVISIONING_KEY` is set on account, as a secret of your own
- [ ] `APP_API_TOKEN` and `ALLOW_INSECURE_DEV_SECRETS` are **not** set on any
      container app
- [ ] Dapr is enabled on report, journal and stock
- [ ] `./scripts/azure-pubsub-resiliency.sh -g <RESOURCE_GROUP> -e <ENVIRONMENT>` passes
      (see Pub/sub redelivery and dead letters)
- [ ] `./scripts/azure-slack-webhook.sh ...` passes: report, journal and stock read
      `SLACK_WEBHOOK_URL` from Key Vault (see Slack webhook from Key Vault)

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

**Cart and the cart store key (#332).** From the release with #332, cart keeps carts in the cart store under `<tenant_id>:<cart_id>`. It still reads a cart from the old bare `<cart_id>` key, and moves it on its next save, deleting the bare key.

- Switch cart's traffic to the new revision at once. Do not split traffic between an old and a new revision.
- While both revisions serve, a request that reaches the old revision for a cart created or moved by the new one answers 404 (cart not found). Carts never diverge into two copies.
- Rolling back cart past #332 has the same effect: the old version cannot read the carts saved under the new key, so carts in flight answer 404 and have to be started again.

**Settlement at close (#343).** From the release with #343, terminal's close asks report to confirm the session's settlement, and daily reports answer from the settled sessions only.

- Update report before terminal (Option B does). A terminal without report's settlement endpoint refuses every close with 503 / `406016`; the terminal stays open, and the close succeeds once report is updated.
- Sessions settled before this release have no settlement record, so a daily report that covers one answers 403 / `412101` (data.unsettledSessions names them). Print or export the daily reports you need before the release.
- report adds the settlement collections and indexes to existing tenants at startup (index ensure on startup).

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
      `SECRET_KEY`, `PUBSUB_NOTIFY_API_KEY`, `APP_API_TOKEN` or
      `TENANT_PROVISIONING_KEY` (empty, or a published value)
- [ ] After a test sale, report, journal and stock received it: the sale shows
      in the report and the journal, and no `Refused a request to /api/v1/...`
      warning appears in their logs. That warning on every delivery means the
      sidecar and the app disagree on `APP_API_TOKEN`; the events are retried
      and then kept in the dead-letter queue, not lost
- [ ] Test critical user flows

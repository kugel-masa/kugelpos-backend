---
description: Azure Container Appsへのデプロイを実行
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/deploy <VERSION> [--env <ENVIRONMENT>]`

- `VERSION`: デプロイするバージョンタグ (例: v0.2.1)
- `--env`: 環境指定 (dev/staging/prod) - デフォルト: dev

**Examples:**
- `/deploy v0.2.1` → dev環境にデプロイ
- `/deploy v0.2.1 --env staging` → staging環境にデプロイ
- `/deploy v0.2.1 --env prod` → 本番環境にデプロイ

## Environment Configuration

環境に応じて以下の変数を設定:

| 環境 | DOMAIN | RESOURCE_GROUP | STATUS |
|------|--------|----------------|--------|
| dev | thankfulbeach-66ab2349.japaneast.azurecontainerapps.io | rg-sakura-pos-dev | Available |
| staging | (TBD) | (TBD) | Not configured |
| prod | (TBD) | (TBD) | Not configured |

**Note:** staging/prod環境は後日追加予定。使用時はエラーを返す。

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

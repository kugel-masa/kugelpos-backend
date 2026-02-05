---
description: Build services (all/specific/common package)
---

## User Input

```text
$ARGUMENTS
```

**Usage:** `/build [OPTIONS] [SERVICES...]`

**Examples:**
- `/build` → Build all services
- `/build cart journal` → Build specific services only
- `/build --with-common` → Common package + all services
- `/build --common-only` → Common package only
- `/build --no-cache` → Build without cache
- `/build --parallel` → Parallel build

## Build Options

| Option | Description |
|--------|-------------|
| `--with-common` | Build common package first, then all services |
| `--common-only` | Build common package only (skip services) |
| `--no-cache` | Build without Docker cache |
| `--parallel` | Parallel build (faster but logs are mixed) |
| `--increment-version` | Increment common package version |

## Available Services

| Service | Port | Description |
|---------|------|-------------|
| account | 8000 | User authentication |
| terminal | 8001 | Terminal management |
| master-data | 8002 | Product catalog |
| cart | 8003 | Shopping cart |
| report | 8004 | Sales reports |
| journal | 8005 | Transaction log |
| stock | 8006 | Inventory |

## Build Commands

### 1. Build All Services (Docker)
```bash
cd scripts && ./build.sh
```

### 2. Build Specific Services Only
```bash
cd scripts && ./build.sh cart journal
```

### 3. Common Package + All Services
```bash
# Build & distribute common package, rebuild pipenv environments
./scripts/update_common_and_rebuild.sh

# Then build Docker images
cd scripts && ./build.sh
```

### 4. Common Package Only
```bash
# Build only
./scripts/run_build_common.sh

# Build & distribute to all services
./scripts/run_build_common.sh && ./scripts/run_copy_common.sh
```

### 5. Build with Version Increment
```bash
./scripts/update_common_and_rebuild.sh --increment-version
```

### 6. No Cache / Parallel Build
```bash
cd scripts && ./build.sh --no-cache
cd scripts && ./build.sh --parallel
cd scripts && ./build.sh --no-cache --parallel cart report
```

## Typical Workflows

### During Development (After Code Changes)
```bash
# Rebuild specific service only
cd scripts && ./build.sh cart
```

### After Common Package Changes
```bash
# Apply common package to all services
./scripts/update_common_and_rebuild.sh
```

### Clean Build
```bash
cd scripts && ./build.sh --no-cache
```

### Before Release
```bash
# Version bump + full build
./scripts/update_common_and_rebuild.sh --increment-version
cd scripts && ./build.sh
```

## Notes

- After build, start services with `./scripts/start.sh`
- On build errors, check logs with `docker-compose logs <service>`
- To rebuild pipenv only: `./scripts/rebuild_pipenv.sh`

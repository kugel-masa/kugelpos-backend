# Quick Start Guide - Cart Performance Tests

> **📢 NEW:** As of the latest update, all tests use **Multi-Terminal Mode** by default!
>
> - Each user gets a unique terminal_id → No lock contention
> - More accurate performance measurements
> - See [QUICKSTART_MULTI_TERMINAL.md](./QUICKSTART_MULTI_TERMINAL.md) for multi-terminal specific guide
> - See [MULTI_TERMINAL_TESTING.md](./MULTI_TERMINAL_TESTING.md) for detailed explanation

## 1. Setup (First Time Only)

### Step 1: Prepare Environment File

```bash
# From project root
cp .env.test.sample .env.test

# Edit .env.test with your configuration
nano .env.test
```

Required variables in `.env.test`:
```bash
TENANT_ID=your_tenant_id
LOCAL_TEST=True  # or False for remote
REMOTE_URL=your_remote_url  # if LOCAL_TEST=False
```

### Step 2: Install Dependencies

```bash
cd services/cart
pipenv install --dev
```

### Step 3: Start Services

```bash
# From project root
cd scripts
./start.sh

# Wait for services to be ready (check health)
curl http://localhost:8003/health
```

## 2. Run Performance Tests

### Option A: Run All Test Patterns (Recommended)

```bash
cd services/cart/performance_tests
./run_perf_test.sh
```

This will run:
1. Pattern 1: 20 users for 5 minutes
2. (30 second wait)
3. Pattern 2: 40 users for 5 minutes

### Option B: Run Individual Patterns

```bash
# Pattern 1 only (20 users)
./run_perf_test.sh pattern1

# Pattern 2 only (40 users)
./run_perf_test.sh pattern2
```

### Option C: Web UI Mode (Interactive)

```bash
cd services/cart/performance_tests
pipenv run locust -f locustfile.py --host=http://localhost:8003
```

Then open: http://localhost:8089

## 3. View Results

Results are saved in `services/cart/performance_tests/results/`:

```bash
cd services/cart/performance_tests/results

# List all reports
ls -lh

# Open HTML report in browser
firefox Pattern_1_20users_*.html  # Linux
open Pattern_1_20users_*.html     # macOS
start Pattern_1_20users_*.html    # Windows
```

## 4. Customize Tests

### Change Number of Items

```bash
export PERF_TEST_ITEMS_PER_CART=10  # Default: 20
./run_perf_test.sh
```

### Change Timing

```bash
export PERF_TEST_ITEM_ADD_INTERVAL=3     # Default: 5 seconds
export PERF_TEST_POST_CANCEL_WAIT=2      # Default: 5 seconds
./run_perf_test.sh
```

### Change Load Pattern

```bash
export PERF_TEST_NUM_USERS=100    # Default: 20
export PERF_TEST_SPAWN_RATE=10    # Default: 2
export PERF_TEST_RUN_TIME=10m     # Default: 5m
./run_perf_test.sh
```

## 5. Troubleshooting

### Problem: API_KEY not found

**Solution:**
```bash
# Check .env.test exists
ls -la .env.test

# If not, create from sample
cp .env.test.sample .env.test
```

### Problem: Connection refused

**Solution:**
```bash
# Check if cart service is running
curl http://localhost:8003/health

# If not, start services
cd scripts
./start.sh

# Check logs
cd ../services
docker-compose logs -f cart
```

### Problem: High failure rate in results

**Solutions:**
1. Reduce number of users
   ```bash
   export PERF_TEST_NUM_USERS=10
   ```

2. Increase spawn rate interval (slower ramp-up)
   ```bash
   export PERF_TEST_SPAWN_RATE=1
   ```

3. Check service logs for errors
   ```bash
   docker-compose logs -f cart mongodb redis
   ```

## 6. Clean Up

### Stop Services

```bash
cd scripts
./stop.sh
```

### Delete Test Results

```bash
cd services/cart/performance_tests/results
rm -f *.html *.csv
```

## Example Complete Workflow

```bash
# 1. Setup (first time)
cp .env.test.sample .env.test
nano .env.test  # Edit with your values

# 2. Install dependencies
cd services/cart
pipenv install --dev

# 3. Start services
cd ../../scripts
./start.sh

# 4. Run performance tests
cd ../services/cart/performance_tests
./run_perf_test.sh

# 5. View results
cd results
ls -lh
firefox Pattern_1_20users_*.html

# 6. Clean up
cd ../../../scripts
./stop.sh
```

## Next Steps

For more advanced usage, see [README.md](./README.md)

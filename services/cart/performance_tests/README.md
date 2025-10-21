# Cart Service Performance Tests

This directory contains performance tests for the Cart Service using [Locust](https://locust.io/), a modern load testing tool.

## 🎯 Multi-Terminal Mode (Default)

**IMPORTANT:** As of the latest update, all performance tests use **Multi-Terminal Mode** by default.

### What is Multi-Terminal Mode?

- Each Locust user is assigned a **unique terminal_id**
- Prevents `threading.Lock()` contention on `transaction_no` generation
- More realistic testing (simulates multiple POS terminals in real stores)
- Significantly more accurate performance measurements

### Why is this important?

**Previous (Single-Terminal) Mode:**
- All users shared one `terminal_id` → Lock contention
- High response time variability (CV > 100%)
- Unrealistic performance bottleneck

**Current (Multi-Terminal) Mode:**
- Each user has unique `terminal_id` → No lock contention
- Low response time variability (CV < 50% expected)
- Accurate representation of real-world usage

## Overview

The performance tests simulate realistic cart operations:

1. **Create Cart** - Initialize a new shopping cart
2. **Add Items (x20)** - Add 20 items with 5-second intervals between each item
3. **Cancel Cart** - Cancel the cart transaction
4. **Wait** - Wait 5 seconds before repeating the scenario

## Test Patterns

Two predefined test patterns are available:

| Pattern | Users | Spawn Rate | Duration | Description |
|---------|-------|------------|----------|-------------|
| **Pattern 1** | 20 | 2/sec | 5 minutes | Moderate load test |
| **Pattern 2** | 40 | 4/sec | 5 minutes | High load test |

## Prerequisites

1. **Environment Setup**
   - Ensure `.env.test` file exists in project root with required variables:
     ```bash
     TENANT_ID=your_tenant_id
     API_KEY=your_api_key
     BASE_URL_CART=http://localhost:8003  # Optional, defaults to localhost
     ```

2. **Install Dependencies**
   ```bash
   cd services/cart
   pipenv install --dev
   ```

3. **Start Cart Service**
   ```bash
   # From project root
   cd scripts
   ./start.sh

   # Or start cart service individually
   cd services
   docker-compose up -d cart mongodb redis
   ```

## Quick Start

### Option 1: Automated Test Execution (Recommended)

```bash
cd services/cart/performance_tests

# Run all patterns with automatic setup/cleanup
# Multi-terminal mode is automatically enabled
./run_perf_test.sh
```

This will:
1. Create 50 terminals (multi-terminal mode)
2. Run Pattern 1 (20 users) and Pattern 2 (40 users)
3. Clean up test data

### Option 2: Manual Setup + Test

```bash
# Step 1: Setup test data with multi-terminal mode (creates 50 terminals by default)
./run_perf_test.sh setup

# Or specify number of terminals
./run_perf_test.sh setup 100

# Step 2: Run specific pattern
./run_perf_test.sh pattern1   # 20 users
./run_perf_test.sh pattern2   # 40 users

# Or custom pattern
./run_perf_test.sh custom 50 10m   # 50 users for 10 minutes

# Step 3: Cleanup when done
./run_perf_test.sh cleanup
```

### Option 3: Multiple Patterns Test

```bash
# Run 20, 30, 40, 50 user tests sequentially
./run_multiple_tests.sh
```

This will:
- Run each pattern with service restart
- Backup results to `results_backup/TIMESTAMP/`
- Generate comparison report

### Show Help

```bash
./run_perf_test.sh help
```

## Advanced Usage

### Web UI Mode (Interactive)

For interactive testing with real-time charts:

```bash
cd services/cart/performance_tests

# First, setup test data (multi-terminal mode)
./run_perf_test.sh setup 100

# Then run Locust Web UI with multi-terminal mode
pipenv run locust -f locustfile_multi_terminal.py --host=http://localhost:8003
```

Then open http://localhost:8089 in your browser and configure:
- Number of users
- Spawn rate
- Host URL (pre-filled)

**Note:** Make sure to run `setup` first to create `terminals_config.json` for multi-terminal mode.

### Single-Terminal Mode (For Comparison Only)

To test single-terminal performance (for comparison with multi-terminal):

```bash
# Use the original locustfile
pipenv run locust -f locustfile.py --host=http://localhost:8003
```

⚠️ **Warning:** Single-terminal mode has lock contention issues and is not recommended for production testing.

### Custom Parameters via Environment Variables

Override default test parameters:

```bash
# Custom scenario parameters
export PERF_TEST_ITEMS_PER_CART=10        # Default: 20
export PERF_TEST_ITEM_ADD_INTERVAL=3      # Default: 5 seconds
export PERF_TEST_POST_CANCEL_WAIT=2       # Default: 5 seconds

# Custom test execution parameters
export PERF_TEST_NUM_USERS=50             # Default: 20
export PERF_TEST_SPAWN_RATE=5             # Default: 2
export PERF_TEST_RUN_TIME=10m             # Default: 5m

# Run with custom parameters
./run_perf_test.sh
```

### Direct Locust Command

Run Locust directly with custom arguments:

```bash
cd services/cart/performance_tests

# Example: 100 users, 10 users/sec spawn rate, 10 minute duration
pipenv run locust \
    -f locustfile.py \
    --host=http://localhost:8003 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 10m \
    --headless \
    --html=results/custom_test.html
```

## Output and Reports

Test results are saved to the `results/` directory:

```
performance_tests/results/
├── Pattern_1_20users_20250118_143022.html          # HTML report
├── Pattern_1_20users_20250118_143022_stats.csv     # Request statistics
├── Pattern_1_20users_20250118_143022_history.csv   # Time-series data
├── Pattern_1_20users_20250118_143022_failures.csv  # Failure details
├── Pattern_2_40users_20250118_144522.html
└── ...
```

### Understanding the Reports

**HTML Report** (`*.html`)
- Summary statistics (requests, failures, response times)
- Response time charts
- Requests per second charts
- Detailed request statistics table

**Stats CSV** (`*_stats.csv`)
- Request type, name, count
- Failure count and rate
- Response time metrics (min, max, median, 95th percentile)
- Requests per second

**History CSV** (`*_history.csv`)
- Time-series data at 1-second intervals
- User count over time
- Request rate over time
- Response time over time

## Configuration

### Test Scenario Configuration

Edit `config.py` to modify default values:

```python
@dataclass
class PerformanceTestConfig:
    # Authentication
    api_key: str
    tenant_id: str

    # Test scenario parameters
    items_per_cart: int = 20        # Number of items per cart
    item_add_interval: int = 5       # Seconds between item additions
    post_cancel_wait: int = 5        # Seconds after cart cancellation

    # Test execution parameters
    num_users: int = 20              # Concurrent users
    spawn_rate: int = 2              # Users spawned per second
    run_time: str = "5m"             # Test duration

    # Target URL
    base_url: str = "http://localhost:8003"
```

### Test Patterns

Modify test patterns in `config.py`:

```python
TEST_PATTERNS = {
    "pattern1": {
        "PERF_TEST_NUM_USERS": "20",
        "PERF_TEST_SPAWN_RATE": "2",
        "PERF_TEST_RUN_TIME": "5m",
        "description": "20 concurrent users for 5 minutes"
    },
    "pattern2": {
        "PERF_TEST_NUM_USERS": "40",
        "PERF_TEST_SPAWN_RATE": "4",
        "PERF_TEST_RUN_TIME": "5m",
        "description": "40 concurrent users for 5 minutes"
    }
}
```

## Troubleshooting

### API_KEY or TENANT_ID not found

Ensure `.env.test` file exists in project root:
```bash
cp .env.test.sample .env.test
# Edit .env.test with your values
```

### Connection Refused

1. Check if cart service is running:
   ```bash
   curl http://localhost:8003/health
   ```

2. Check docker containers:
   ```bash
   cd services
   docker-compose ps
   ```

3. Check logs:
   ```bash
   docker-compose logs -f cart
   ```

### High Failure Rate

- Check MongoDB and Redis are running
- Check service logs for errors
- Reduce number of concurrent users
- Increase spawn rate interval (spawn users more slowly)

### Locust Not Installed

```bash
cd services/cart
pipenv install --dev
```

## Performance Metrics

### Key Metrics to Monitor

1. **Response Time**
   - 50th percentile (median): Typical user experience
   - 95th percentile: Worst-case for 95% of users
   - 99th percentile: Worst-case for 99% of users

2. **Requests per Second (RPS)**
   - Total RPS: System throughput
   - Per-endpoint RPS: Identify bottlenecks

3. **Failure Rate**
   - Should be 0% or very low (<1%)
   - High failure rate indicates system overload

4. **User Load**
   - Maximum users the system can handle
   - At what point does performance degrade?

### Example Baseline Metrics

These are example targets (adjust based on requirements):

- **Response Time (95th percentile)**
  - Create Cart: < 500ms
  - Add Item: < 300ms
  - Cancel Cart: < 400ms

- **Throughput**
  - 20 users: > 100 RPS
  - 40 users: > 200 RPS

- **Failure Rate**
  - All patterns: < 0.1%

## Best Practices

1. **Run tests during low-traffic periods** to avoid affecting production
2. **Start with lower load** (Pattern 1) before running higher load tests
3. **Monitor system resources** (CPU, memory, database) during tests
4. **Establish baselines** before making performance improvements
5. **Compare results** after optimization changes
6. **Clean test data** between runs if needed

## Related Documentation

- [Locust Documentation](https://docs.locust.io/)
- [Cart Service API Documentation](../app/api/v1/cart.py)
- [Project Main README](../../../README.md)

## License

Copyright 2025 masa@kugel

Licensed under the Apache License, Version 2.0

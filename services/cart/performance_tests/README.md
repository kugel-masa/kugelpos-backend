# Cart Service Performance Tests

Performance testing tools for the Cart Service using [Locust](https://locust.io/).

## Directory Structure

```
performance_tests/
├── scripts/                    # Execution scripts
│   ├── run_perf_test.sh       # Main test runner
│   └── run_multiple_tests.sh  # Sequential multi-pattern execution
├── results/                    # Test result output
├── results_backup/             # Result backups
├── locustfile.py              # Test scenarios
├── setup_test_data.py         # Test data setup
├── cleanup_test_data.py       # Test data cleanup
├── config.py                  # Configuration
├── generate_item_chart.py     # Chart generation
└── generate_comparison_report.py # Comparison report generation
```

## Quick Start

### 1. Install Dependencies

```bash
cd services/cart
pipenv install --dev
```

### 2. Start Services

```bash
cd scripts
./start.sh
```

### 3. Run Tests

```bash
cd services/cart/performance_tests

# Fully automated execution (setup → test → cleanup)
./scripts/run_perf_test.sh all

# Or manual steps
./scripts/run_perf_test.sh setup 50    # Create 50 terminals
./scripts/run_perf_test.sh pattern1    # 20 users × 5 min
./scripts/run_perf_test.sh pattern2    # 40 users × 5 min
./scripts/run_perf_test.sh cleanup     # Cleanup
```

## Test Scenario

Each virtual user repeats the following flow:

1. **Create Cart** - `POST /api/v1/carts`
2. **Add Items × 20** - `POST /api/v1/carts/{id}/lineItems` (3-second intervals)
3. **Cancel Cart** - `POST /api/v1/carts/{id}/cancel`
4. **Wait** - Return to step 1 after 3 seconds

## Test Patterns

| Pattern | Users | Spawn Rate | Duration |
|---------|-------|------------|----------|
| pattern1 | 20 | 2/sec | 5 min |
| pattern2 | 40 | 4/sec | 5 min |
| custom | any | auto | any |

### Custom Pattern

```bash
./scripts/run_perf_test.sh custom 100 10m  # 100 users × 10 min
```

## Configuration

Override settings via environment variables:

```bash
export PERF_TEST_NUM_USERS=50        # Number of users
export PERF_TEST_SPAWN_RATE=5        # Spawn rate (/sec)
export PERF_TEST_RUN_TIME=10m        # Run time
export PERF_TEST_ITEMS_PER_CART=10   # Items per cart
export PERF_TEST_ITEM_ADD_INTERVAL=2 # Item add interval (sec)
```

## Multi-Terminal Mode

Tests run in **multi-terminal mode**:

- Each Locust user is assigned a unique `terminal_id`
- Avoids `threading.Lock()` contention
- Simulates realistic store operations (multiple POS terminals)

## Web UI Mode

For interactive testing:

```bash
# After setup
./scripts/run_perf_test.sh setup 50

# Start Web UI
cd services/cart/performance_tests
pipenv run locust -f locustfile.py --host=http://localhost:8003
```

Open http://localhost:8089 in your browser

## Output Files

Results are saved to `results/`:

| File | Description |
|------|-------------|
| `*.html` | HTML report (with charts) |
| `*_stats.csv` | Request statistics |
| `*_stats_history.csv` | Time-series data |
| `*_failures.csv` | Failure details |
| `*_add_item.html` | Item addition chart |

## Sequential Multi-Pattern Execution

Run multiple user count patterns sequentially for benchmarking and generate comparison reports.

### How to Run

```bash
./scripts/run_multiple_tests.sh
```

### Execution Flow

For each pattern, the following is automatically executed:

1. Restart services (`scripts/stop.sh` → `scripts/start.sh`)
2. Cleanup previous test data
3. Setup test data (terminals = users + 10)
4. Run performance test (10 minutes)
5. Backup results to `results_backup/YYYYMMDD_HHMMSS/`
6. Cleanup test data

### Default Patterns

| Pattern | Users | Terminals | Duration |
|---------|-------|-----------|----------|
| 1 | 20 | 30 | 10 min |
| 2 | 30 | 40 | 10 min |
| 3 | 40 | 50 | 10 min |
| 4 | 50 | 60 | 10 min |

### Estimated Time

Approximately 1-1.5 hours (including setup/cleanup)

### Output

```
results_backup/
└── 20260204_153000/
    ├── 20users/
    │   ├── Custom_20users_*.html
    │   └── Custom_20users_*.csv
    ├── 30users/
    ├── 40users/
    ├── 50users/
    └── comparison_report_*.html    # Comparison report
```

### Comparison Report

An HTML report comparing all patterns is automatically generated:

- Response time comparison across patterns
- Throughput comparison
- Failure rate comparison

### Changing Patterns

Edit lines 71-72 in `scripts/run_multiple_tests.sh`:

```bash
TEST_PATTERNS=(20 30 40 50)  # Array of user counts
TEST_DURATION="10m"          # Duration for each pattern
```

Examples:

```bash
# Short tests
TEST_PATTERNS=(10 20)
TEST_DURATION="5m"

# High load tests
TEST_PATTERNS=(50 100 150 200)
TEST_DURATION="15m"
```

## Troubleshooting

### API_KEY not found

```bash
# .env.test is required
cp .env.test.sample .env.test
```

### Connection refused

```bash
# Check if service is running
curl http://localhost:8003/health
```

### terminals_config.json not found

```bash
# Run setup
./scripts/run_perf_test.sh setup 50
```

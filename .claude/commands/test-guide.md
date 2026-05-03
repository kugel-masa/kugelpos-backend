---
description: Test execution guide and Event Loop issue handling
---

## Test tiers

Each service splits tests into three tiers:

| Tier | Path | External deps | Use when |
|---|---|---|---|
| `unit` | `tests/unit/` | None — all I/O mocked | Tight feedback loops, ideally < 10s/service |
| `integration` | `tests/integration/` | Real MongoDB only | Repository / aggregation logic against real DB |
| `e2e` | `tests/e2e/` | Full docker-compose stack | API-to-pubsub flows, inter-service contracts |

Per-tier conftests automatically mark every test in the directory, so new
tests just need to land in the right folder. See `docs/ja/testing-tiers.md`.

## Quick Commands

```bash
# Everything
./scripts/run_unit_tests.sh                          # no MongoDB needed
./scripts/run_integration_tests.sh                   # MongoDB only
./scripts/run_e2e_tests.sh                           # full stack

# Single service, single tier
cd services/<service>
pipenv run pytest -m unit
pipenv run pytest -m integration
pipenv run pytest -m e2e

# Single service, all tiers (legacy entrypoint)
cd services/<service>
./run_all_tests.sh

# Filter by name
pipenv run pytest -m unit -k "test_name"

# Coverage
pipenv run pytest --cov=app tests/
```

`./scripts/run_all_tests_with_progress.sh` still works and runs every
service's full suite (unit + integration + e2e) sequentially.

## Event Loop Closure Issue

### Symptom
```
RuntimeError: Event loop is closed
```
Multiple async tests fail in sequence.

### Root cause
- Global singleton MongoDB client tied to event loop
- pytest-asyncio creates a new event loop per test
- Old client references the closed loop

### How it's handled

`cleanup_database_connection` autouse fixture in the per-service or
parent conftest:

```python
@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_database_connection(set_env_vars):
    yield
    from kugel_common.database import database as db_helper
    await db_helper.reset_client_async()
```

For unit tests, this is overridden to a no-op (no DB to reset).

## Testing Conventions

- Files: `test_*.py` under `tests/unit/`, `tests/integration/`, or `tests/e2e/`
- Test ordering for e2e (e.g. `test_setup_data` first) is enforced via
  `pytest_collection_modifyitems` in the tier's conftest, NOT by an
  explicit shell-level file list
- Async: `pytest-asyncio`
- Cross-service HTTP in integration: mock with `respx`
- JWT in integration: generate locally with `kugel_common`'s helpers
  rather than fetching from a running account service

## Debugging failures

1. **Event-loop errors**: confirm `cleanup_database_connection` fires for the tier
2. **DB connection errors**: ensure MongoDB is running with replica set
3. **Import errors**: run `./scripts/rebuild_pipenv.sh`
4. **"No tests collected"** with `-m <tier>`: directory exists but the
   tier conftest's auto-mark hook hasn't run — check the conftest is in
   place and tests are actually under that directory

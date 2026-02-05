---
description: テスト実行ガイドとEvent Loop問題への対処
---

## Quick Commands

```bash
# All services
./scripts/run_all_tests.sh

# All services with progress
./scritps/run_all_tests_with_progress.sh

# Single service
cd services/<service>
pipenv run pytest tests/ -v
pipenv run pytest tests/ -k "test_name" -v

# With coverage
pipenv run pytest --cov=app tests/
```

## Event Loop Closure Issue (RESOLVED)

### Problem
```
RuntimeError: Event loop is closed
```
Multiple async tests fail in sequence.

### Root Cause
- Global singleton MongoDB client tied to event loop
- pytest-asyncio creates new event loop per test
- Old client references closed event loop

### Solution

`cleanup_database_connection` fixture in `conftest.py` handles this:

```python
@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_database_connection(set_env_vars):
    yield
    from kugel_common.database import database as db_helper
    await db_helper.reset_client_async()
```

**Key:** `autouse=True` = automatic cleanup for all tests.

### Pattern

```python
# ✅ GOOD: No explicit cleanup needed
async def test_something(set_env_vars):
    db = await local_db_helper.get_db_async(db_name)
    # ... test logic ...
    # Fixture handles cleanup automatically
```

## Testing Conventions

- Files: `test_*.py`
- Order: `test_clean_data.py` → `test_setup_data.py` → feature tests
- Async: `pytest-asyncio`
- Fixtures: `conftest.py`

## Debugging Failures

1. **Event loop errors**: Check `cleanup_database_connection` fixture
2. **DB connection errors**: Ensure MongoDB running with replica set
3. **Import errors**: Run `./scripts/rebuild_pipenv.sh`

---
description: Test execution guide and Event Loop issue handling
---

## Test tiers

Each service splits tests into three tiers:

| Tier | Path | External deps | Use when |
|---|---|---|---|
| `unit` | `tests/unit/` | None — all I/O mocked | Tight feedback loops, ideally < 10s/service |
| `integration` | `tests/integration/` | Real MongoDB only | Repository / aggregation logic against real DB |
| `e2e` | `services/<svc>/tests/e2e/` (per-service) or `tests/e2e/` (cross-service) | Full docker-compose stack | API-to-pubsub flows, inter-service contracts |

Per-tier conftests automatically mark every test in the directory, so new
tests just need to land in the right folder. See `docs/ja/testing-tiers.md`.

### Repo-root `tests/e2e/` (cross-service)

The repo-root `tests/e2e/` directory holds **cross-service** scenarios
in its own Pipfile-managed venv. `scripts/run_e2e_tests.sh` runs it
automatically after every per-service e2e suite. Currently houses:

- `test_health_all_services.py` — all services' `/health` reachable
- `test_pos_full_journey.py` — tenant → terminal → cart → payment → tranlog → journal/report
- `test_void_return_journey.py` — void/return sign-flip across cart→journal→report
- `test_pubsub_idempotency.py` — duplicate `event_id` must not double-aggregate
- `test_data_consistency.py` — cart/journal/report totals stay consistent
- `test_auth_boundary.py` — cross-tenant denial + expired/wrong-sig/malformed JWT
- `test_concurrency.py` — concurrent cart ops and pub/sub ordering

To run only the cross-service suite:
```bash
cd tests/e2e && pipenv run pytest -m e2e
```

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

## Cart: DUAL and REQUIRED mode

Cart is mid-migration from a server-held cart to one the client carries on every
mutating request (#156). `CART_REQUEST_SNAPSHOT_MODE` selects which clients are
accepted, and it changes which e2e tests can pass.

| mode | a request that carries its snapshot | one that does not |
|---|---|---|
| `DUAL` (default) | accepted | accepted, served from the cache |
| `REQUIRED` | accepted | **refused, 422 / `401508`** |

That refusal is the point of REQUIRED, not a failure. But 45 of cart's 85 e2e
tests were written against the cache path and hit it, so a plain run under
REQUIRED looks like half the suite broke.

Those 45 carry a `dual_only` mark, so the two runs are:

```bash
# DUAL - the default, nothing special
cd services/cart && pipenv run pytest tests/e2e            # 85 passed

# REQUIRED - deselect what needs the fallback
echo 'CART_REQUEST_SNAPSHOT_MODE=REQUIRED' >> services/cart/.env
./scripts/stop.sh && ./scripts/start.sh                    # REQUIRED
cd services/cart && pipenv run pytest tests/e2e -m "not dual_only"
                                                           # 40 passed, 45 deselected
```

**The restart is the step that gets skipped.** A container reads its environment
once, at start; editing `.env` under a running stack changes nothing, the suite
passes as DUAL, and the run gets recorded as a REQUIRED verification it never
was. Confirm before trusting a result:

```bash
docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE
```

Revert by deleting the line and restarting. `services/cart/.env` is gitignored,
so this is a local change; the setting is documented in `.env.sample`.

REQUIRED is not part of routine work — run it when moving #156 forward, after
rewriting a `dual_only` test, or before switching a deployment over. The count of
`dual_only` marks is what the migration has left to do, and the end state is that
the mark disappears entirely.

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
- `dual_only` (cart e2e only): the test drives the cart without carrying its
  snapshot, so it needs the phase 1 fallback and cannot pass under
  `CART_REQUEST_SNAPSHOT_MODE=REQUIRED` - see the mode section above
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

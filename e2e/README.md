# Top-level E2E test directory

This directory is reserved for **cross-service** end-to-end scenarios — tests
that exercise a business flow spanning multiple services in a single test
file (for example: "create terminal → open business day → ring up cart →
pay → tranlog publishes → journal records → report aggregates").

## Why a separate directory

Per-service e2e tests live under each service's `tests/e2e/` and verify that
service's own API/lifecycle against a running stack. They naturally touch
neighbouring services (for example, cart's e2e tests expect master-data and
account to be live) but their assertions are scoped to the service under
test.

Tests here, by contrast, are written against the *system as a whole*: they
make claims about cross-service contracts, ordering, and data flow that
no single service owns.

## What's here

| File | Purpose |
|---|---|
| `test_health_all_services.py` | Smoke check that every service's `/health` endpoint responds 200 once the stack is up |
| `test_pos_full_journey.py` | End-to-end POS flow: tenant setup → terminal open → cart → payment → tranlog publish → journal & report aggregation |
| `test_void_return_journey.py` | Void / return scenarios across cart → journal → report (sign-flip semantics) |
| `test_pubsub_idempotency.py` | Re-delivery of the same `event_id` on `tranlog_report` must NOT double-aggregate (state-store idempotency check) |
| `test_data_consistency.py` | Cross-service data invariants — totals in cart match journal entries match report aggregates |
| `test_auth_boundary.py` | Security perimeter: cross-tenant denial, expired / wrong-signature / malformed JWT all yield 401/403 |
| `test_concurrency.py` | Concurrent cart operations and pub/sub ordering under load |

These are managed via this directory's own `Pipfile` (separate venv) and run
after the per-service e2e suites by `scripts/run_e2e_tests.sh`.

## How to run

```bash
# All e2e (per-service + cross-service)
./scripts/run_e2e_tests.sh

# Just the cross-service tests
cd e2e
pipenv run pytest -m e2e
```

The runner auto-detects this directory: it executes the cross-service suite
when both a `Pipfile` and `test_*.py` files are present.

## Conventions

- Mark every test with `@pytest.mark.e2e` (or rely on a `pytest_collection_modifyitems`
  hook in a future `conftest.py`).
- Assume the full docker-compose stack is up — these tests are not expected
  to be runnable against a partial environment.
- Keep tests focused on the cross-service contract; if a test could just as
  well live in one service's `tests/e2e/`, prefer that.

See `docs/ja/testing-tiers.md` for the full 3-tier model.

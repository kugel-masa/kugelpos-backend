# Repo-root E2E test directory

This directory (`tests/e2e/` at the repo root) holds **cross-service**
end-to-end scenarios — tests that exercise a business flow spanning
multiple services in a single test file (for example: "create terminal
→ open business day → ring up cart → pay → tranlog publishes → journal
records → report aggregates").

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
| `test_dead_letter_journey.py` | Dead letters (#230): give up, record, notify once, replay; a close log that cannot finalize; the dlq and shovel path; the sweep. Needs the overlay below, skips without it |

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

## Dead-letter journey (#230)

`test_dead_letter_journey.py` needs the stack started with an overlay that makes
report, journal and stock give up on the 2nd failure, has their sidecars retry 3
times 2 seconds apart, runs the dead-letter sweep every 5 seconds, and sends Slack
notifications to a local sink (`http://localhost:8099/messages`) the tests read:

```bash
cd services
docker compose -f docker-compose.yaml -f docker-compose.e2e-deadletter.yaml up -d
cd ../tests/e2e
pipenv run pytest test_dead_letter_journey.py
# Back to the normal stack afterwards
cd ../../services
docker compose -f docker-compose.yaml up -d --remove-orphans
```

Without the overlay the sink is not there and the tests skip, so
`./scripts/run_e2e_tests.sh` on the normal stack passes over them. The tests
inject faults with MongoDB collection validators on the tenant databases they
create, and take them off again. The "could not be recorded" notice is sent at
most once per service process every 5 minutes, so the test accepts a run
within 5 minutes of the last one sending none.

## Conventions

- Mark every test with `@pytest.mark.e2e` (or rely on a `pytest_collection_modifyitems`
  hook in a future `conftest.py`).
- Assume the full docker-compose stack is up — these tests are not expected
  to be runnable against a partial environment.
- Keep tests focused on the cross-service contract; if a test could just as
  well live in one service's `tests/e2e/`, prefer that.

See `docs/ja/testing-tiers.md` for the full 3-tier model.

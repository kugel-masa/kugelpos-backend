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

## Status

**Empty as of issue #109.** Existing cross-service coverage is currently
spread across the per-service `tests/e2e/` directories. As the codebase
evolves, scenarios that prove difficult to attribute to one service should
land here instead of being duplicated across them.

## How to run

Once tests land here:

```bash
./scripts/run_e2e_tests.sh
```

The script runs each service's `tests/e2e/` and then this directory.

## Conventions

- Mark every test with `@pytest.mark.e2e` (or rely on a `pytest_collection_modifyitems`
  hook in a future `conftest.py`).
- Assume the full docker-compose stack is up — these tests are not expected
  to be runnable against a partial environment.
- Keep tests focused on the cross-service contract; if a test could just as
  well live in one service's `tests/e2e/`, prefer that.

See `docs/ja/testing-tiers.md` for the full 3-tier model.

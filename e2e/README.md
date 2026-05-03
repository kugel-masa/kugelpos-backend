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

**Empty as of issue #109.** The cross-service flows that fit this
directory's purpose (e.g. cart → tranlog publish → journal subscribe → report
aggregate) are currently exercised end-to-end by the per-service `tests/e2e/`
suites — `cart/tests/e2e/test_cart.py` runs the cart flow which then
populates journal and report through Dapr pub/sub, and report's e2e suite
asserts on the resulting aggregates.

Promoting those scenarios into authoritative top-level tests is **deferred
to a follow-up PR**: it requires both (a) a separate Pipfile-managed venv
under `/e2e/` and (b) careful identification of which assertions belong to
the cross-service contract vs. each service's own contract.

## How to run

Once tests land here:

```bash
./scripts/run_e2e_tests.sh
```

The script auto-detects this directory and runs it after every per-service
e2e suite, but only when both a `Pipfile` and `test_*.py` files are present.

## Conventions

- Mark every test with `@pytest.mark.e2e` (or rely on a `pytest_collection_modifyitems`
  hook in a future `conftest.py`).
- Assume the full docker-compose stack is up — these tests are not expected
  to be runnable against a partial environment.
- Keep tests focused on the cross-service contract; if a test could just as
  well live in one service's `tests/e2e/`, prefer that.

See `docs/ja/testing-tiers.md` for the full 3-tier model.

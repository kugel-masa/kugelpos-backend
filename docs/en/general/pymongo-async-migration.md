# Porting Guide: Motor to the PyMongo Async API

Motor was deprecated on 2026-05-14 and receives critical fixes only until
**2027-05-14**. Kugelpos moved every service and `kugel_common` to the PyMongo
async API (`pymongo.AsyncMongoClient`) in issue #301. This guide is for a tree
that shares this codebase and has to make the same move: what to change, in
which order, and how to know each step is done.

The move changes no behaviour: the same API responses, the same stored data
(BSON is unchanged), the same indexes. No data migration is needed.

## 1. What changes

### 1.1 Renames you can do mechanically

| Motor | PyMongo async |
|---|---|
| `from motor.motor_asyncio import AsyncIOMotorClient` | `from pymongo import AsyncMongoClient` |
| `AsyncIOMotorDatabase` | `pymongo.asynchronous.database.AsyncDatabase` |
| `AsyncIOMotorCollection` | `pymongo.asynchronous.collection.AsyncCollection` |
| `AsyncIOMotorClientSession` | `pymongo.asynchronous.client_session.AsyncClientSession` |
| `AsyncIOMotorCursor` | `pymongo.asynchronous.cursor.AsyncCursor` |

Exceptions stay in `pymongo.errors`. `find()` still returns a cursor without
`await`; `find_one`, `insert_*`, `update_*`, `delete_*`, `count_documents`,
`distinct`, `create_index`, `index_information`, `list_collection_names`,
`command`, `drop_database` and `server_info` are awaited as before, and
`async for doc in cursor` still works.

### 1.2 Calls that change shape (decide each one by hand)

| Call | Motor | PyMongo async |
|---|---|---|
| `client.start_session()` | awaited | **not awaited**, returns the session |
| `session.start_transaction()` | synchronous | **awaited** |
| `collection.aggregate(...)` | returns the cursor | **awaited**, then returns the cursor |
| `collection.list_indexes()` | returns the cursor | **awaited**, then returns the cursor |
| `client.close()` | synchronous | **awaited** |
| `cursor.to_list(0)` | returns an empty list | **raises `ValueError`** |

A missing `await` on these does not always fail loudly:

- `client.close()` without `await` only warns (`coroutine ... was never
  awaited`); the client stays open.
- `aggregate()` without `await` gives a coroutine instead of a cursor:
  `async for` over it raises `TypeError`, and a chained `.to_list()` raises
  `AttributeError`. Code that wraps the call in a broad `except` turns either
  into an empty result.
- `session.start_transaction()` without `await` opens no transaction. Every
  write then commits on its own. A later `commit_transaction()` fails with
  `InvalidOperation: No transaction started`, but the writes are already in
  the database; an abort guarded by `session.in_transaction` passes silently
  and leaves them in place. Check that an abort leaves nothing.
- For `to_list(0)`, decide what the call meant. Motor returned an empty list;
  if the code relied on that, keep it explicit. If it meant "no limit" (as this
  tree's repositories do, mapping 0 to an unlimited fetch before the cursor),
  pass `None`. Swapping 0 for `None` blindly turns a call that returned nothing
  into one that returns the whole collection.

`session.commit_transaction()`, `abort_transaction()` and `end_session()` are
awaited in both drivers. `async with session:` works in both.

### 1.3 A client belongs to one event loop

A PyMongo async client can be used, and closed, only on the event loop that
created it. Awaiting `close()` from another loop raises `RuntimeError` (Motor
did not). This matters wherever loops change:

- **Test suites that use a new loop per test.** Close the shared client at the
  end of each test, in that test's own loop (a function-scoped fixture's
  teardown). Do not leave it for the next test to discard.
- **A module-level `asyncio.Lock`** guarding client creation. A lock binds to
  the first loop that waits on it, so one lock for the module refuses every
  later loop. Keep one lock per loop.
- **Code that makes its own client** (a scheduler job, a script) must close it
  in the same loop, in a `finally`, or use the shared client instead.

In this tree, `kugel_common.database.database` remembers the loop with the
client. `close_client_async()` and `reset_client_async()` close the client when
called on that loop. Called from another loop, they drop the reference with a
warning (`created on another event loop`), because closing it there would raise.
`get_client_async()` called from another loop drops the old client the same way
and makes a new one. Seeing that warning means a client outlived the loop it
was made for, so a test run should not show it.

Uvicorn workers are separate processes and APScheduler's `AsyncIOScheduler`
runs on the application's loop, so neither needs anything new.

## 2. Finding what to change

Search case-insensitively, and go through each hit by hand:

```bash
# Imports and types
grep -rn -i "motor" --include=*.py . | grep -v "/.venv/"

# Calls that change shape
grep -rn -E "\.(aggregate|list_indexes|close|start_session|start_transaction)\(" --include=*.py . | grep -v "/.venv/"
grep -rn -E "to_list\(" --include=*.py . | grep -v "/.venv/"     # any value that can be 0?

# Motor-only APIs: not used in this tree, but check yours
grep -rn -i -E "io_loop|get_io_loop|\.each\(|stream_to_handler|\.watch\(|GridFS|motor_gridfs|delegate" --include=*.py . | grep -v "/.venv/"

# Clients made outside the shared helper (who closes them, and on which loop?)
grep -rn "AsyncIOMotorClient(\|AsyncMongoClient(" --include=*.py . | grep -v "/.venv/"
```

For each hit of the last two searches, decide whether the call needs an
`await`, a `finally: await client.close()`, or the shared client. `.watch()`
(change streams) and GridFS have their own PyMongo async equivalents; read the
[official migration guide](https://www.mongodb.com/docs/languages/python/pymongo-driver/reference/migration/)
for those.

### Test doubles

A test that patches Motor will not fail when Motor goes away; it stops testing
anything. Go through them one by one:

- `patch("motor.motor_asyncio.AsyncIOMotorClient")` patched Motor's module.
  Patch the name the code under test actually looks up, for example
  `app.services.some_module.get_client_async`, and assert that the double was
  used.
- `monkeypatch.setattr(database, "AsyncIOMotorClient", Fake)` becomes
  `AsyncMongoClient`. Give the fake an `async def close()`.
- A fake collection whose `aggregate` / `list_indexes` is a plain function must
  become `async def`. Otherwise the `await` raises a `TypeError`, a broad
  `except` swallows it, and the test passes without testing anything.
- `MagicMock` for `client.close` must become `AsyncMock`.

## 3. Order

1. **Measure first.** Run the standard performance test (`/perf-test`) on the
   tree before any change, twice. Single-run averages vary by 15–19%, and the
   comparison needs to tell a 10% change apart.
2. **Record the baseline.** Test counts per service and tier, the cart e2e under
   both snapshot modes, and every tenant database's collections and
   `index_information()`. Then create a tenant on the old build and record a
   sale, a cash-in, and the API answers for them, keeping the MongoDB volume.
3. **The common library.** Change the client creation and closing, the session
   start, the aggregation call and the types. Add integration tests against a
   real MongoDB replica set for: aggregation results, commit / abort / `async
   with` sessions, closing on the same loop, twice, and from another loop,
   concurrent `get_client_async`, and `max=0` meaning "no limit". Release a new
   wheel version.
4. **Services.** Do the renames, the shape changes (§1.2), the clients made
   outside the helper, and the test doubles (§2). Run each service's unit and
   integration tests as you go.
5. **Dependencies** (§5).
6. **Verify everything** (§4).
7. **Measure again** under the same conditions and compare.
8. **Docs.** Replace "Motor" in project docs and agent instructions.

Ship it as one change. Services take the common library's database and session
types as they are, so a common library on PyMongo with services on Motor (or
the reverse) does not work part way without a compatibility layer.

## 4. Verifying each step

| Check | How |
|---|---|
| No Motor left | `grep -rn -i motor` over code, Pipfiles, locks and `pyproject.toml` returns nothing |
| Tests | Unit, integration and e2e counts equal the baseline (plus new tests), with no failures. In this tree the cart e2e runs under `DUAL` and `REQUIRED`: restart after setting the mode and confirm it with `docker exec services-cart-1 printenv CART_REQUEST_SNAPSHOT_MODE` |
| Missing `await` | Run unit and integration with `-W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning`. A never-awaited coroutine warns from its finaliser, which pytest reports as `PytestUnraisableExceptionWarning`, so the first flag alone does not fail the run. Then read every hit of the shape-change search |
| Sessions | On a real MongoDB, each code path that opens a transaction is in one right after `start_transaction()` (`session.in_transaction`), and an abort leaves no write |
| Old data | On the new build, with the old volume, the tenant from step 2 answers the same (only generated-on-request fields such as a flash report's timestamp differ), and a void of the old sale, a new sale and a close all succeed |
| Indexes | Collections and `index_information()` per service database equal the baseline |
| Shutdown | Stop the stack and read each service's log: one `Database connection closed`, no `RuntimeError`, no unclosed-client warning. Integration tests do not run the lifespan, so only this check covers shutdown order |
| Performance | Median, p95, p99 and throughput within 10% of the baseline, or explained |

## 5. Dependencies and locks

- `pyproject.toml` of the common library: replace `motor` with `pymongo>=4.13`
  (4.13 is the release where the async API left beta).
- Each Pipfile: replace `motor = "*"` with `pymongo = ">=4.13"`.
- Each Pipfile.lock: PyMongo is already locked as Motor's dependency, with
  every hash. Removing the `motor` entry is enough; adding `"index": "pypi"` to
  the `pymongo` entry makes it look the way `pipenv lock` would write a direct
  dependency. Recompute `_meta.hash.sha256` with pipenv's own calculation
  (`Project().pipfile.calculate_hash()`). If the common library is vendored as
  a wheel, update its file name and hash too. Editing the lock this way keeps
  every other pinned version where it was, so the diff shows only this change.
- `pipenv verify` compares only the Pipfile hash. Also install from the lock
  into an empty environment and check it:

  ```bash
  export WORKON_HOME=$(mktemp -d) PIPENV_VENV_IN_PROJECT=0 PIPENV_IGNORE_VIRTUALENVS=1
  pipenv install --deploy && pipenv run pip check
  pipenv run python -c "from pymongo import AsyncMongoClient"
  pipenv run python -c "import motor"      # must fail
  pipenv --rm
  ```

- Rebuild the images and check inside one that the library version is the new
  one and `motor` is absent.
- Existing development environments still have Motor installed. Remove it
  (`pipenv run pip uninstall -y motor`) so a leftover import fails on your
  machine as well as in CI.

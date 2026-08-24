# Client-Carried Cart (Phase 2)

Covers issue #156 / spec `specs/156-stateless-cart/`, building on phase 1 (issue #148, snapshot issuance).

## Overview

The POS **carries a signed cart snapshot on every mutating request**, and the backend reconstructs the cart from it. The server-side cart cache is no longer the authority, which removes an entire failure class: a Redis timeout or split-brain can no longer lose a transaction in progress.

Phase 1's restore API is functionally subsumed by this and has been removed.

## Request shape

Mutating endpoints accept a wrapped body.

```json
{
  "signedSnapshot": { "kid": "v1", "cart_document": { ... }, "signature": "..." },
  "payload": [ { "itemCode": "49-01", "quantity": 2 } ]
}
```

Middleware peels `signedSnapshot` off and forwards only `payload`, so existing endpoint signatures (such as `list[Item]`) are unchanged.

Requests without a snapshot are still accepted (see migration mode below).

### Compressed requests

Carrying the snapshot makes uploads large enough to be worth compressing, so compressed request bodies are accepted (FR-009).

| Aspect | Detail |
|---|---|
| Encodings | `gzip` / `deflate` / `br` (all standard in .NET 8) |
| Header | `Content-Encoding: gzip` |
| Body ceiling | `MAX_REQUEST_BODY_BYTES` (default 4MB in cart) |
| Over the ceiling | `413` (code `401509`). Enforced *during* expansion, so a small forged body cannot exhaust memory — and against the uncompressed body too, so not compressing is not a way past it (#195) |
| Unsupported encoding | `415`, including chained values such as `gzip, br` |

Compression is optional; uncompressed requests behave as before. Measured, a 50-line cart is 50KB raw, 3.6KB gzipped, 2.9KB with brotli.

Compression saves bandwidth, not ceiling: the limit is enforced against the decompressed size, so a transaction refused uncompressed is refused at the same size when it travels compressed. Measured against the running stack, a 999-line transaction with distinct SKUs carries an 894KB snapshot (55% of it copies of the item masters) and gzips to 19KB; under a 1MB ceiling it was refused at 1,221 lines whether or not it was compressed.

## Migration mode

Switched by the `CART_REQUEST_SNAPSHOT_MODE` environment variable.

| Value | Behaviour |
|---|---|
| `DUAL` (default) | Snapshot-less requests are accepted and served from the server-side cache |
| `REQUIRED` | Snapshot-less mutating requests are rejected (`401508`). Switch to this once every client has migrated |

## Transaction numbering

In phase 2 **`transaction_no` is the per-open sequence (seq)**. `business_counter` is a monotonically increasing epoch that advances each time the terminal opens, and `transaction_no` restarts within each one.

**A transaction is identified by `(tenant_id, store_code, terminal_no, business_counter, transaction_no)`** — `transaction_no` alone does not name one.

| Path | transaction_no | receipt_no | Timestamp |
|---|---|---|---|
| Stateless (snapshot + finalize context carried) | Carried (seq) | Carried | Client-stamped |
| DUAL / legacy (no context) | Server-assigned | Server-assigned | Server clock |

The client carries the numbering so that **a retried finalize yields the same number and time on any backend**. Duplicate finalizes converge to a single record downstream (report / journal / stock) via `cart_id`.

Numbering integrity is backed by a unique index: a second insert of the same `(business_counter, transaction_no)` is refused by the database.

### Carried counters

`business_counter` and `receipt_no` are owned by the terminal, which may advance them during an offline session. They are reconciled with `max()` at open, so a value used offline is never reused (gaps are allowed).

Carried values are bounded. Because the reconcile is irreversible, both an absolute ceiling and a maximum jump above the stored value are enforced, so one malformed client cannot permanently burn the number space.

## Reach of void and return

The two deliberately differ.

| | Reach | Why |
|---|---|---|
| **Void** | This terminal, this business date, this open session | It reverses a sale while the drawer and the day's totals are still open |
| **Return** | Any store, terminal, or past session of the tenant | The customer brings the receipt to whichever store they choose |

Voiding an older transaction is refused with `400` (`401514`) and points at return instead.

The return itself is **booked against the terminal performing it**, not the original's store. The original is recorded in `origin` by store code, terminal number, business counter and transaction number.

### Identifying the original

Since `transaction_no` restarts every open, the transaction get / void / return endpoints accept `business_counter` as a query parameter.

- **Return**: reaches other stores and past sessions, so there is nothing to default to. Omitting it when the number matches several sessions is refused with `409` (`401513`)
- **Void**: reaches only the current session, so omitting it defaults to the current epoch

The receipt prints all four fields needed to identify the original (store code / register / business counter / transaction number).

## Error codes

| Code | HTTP | Meaning |
|---|---|---|
| `401501` | 400 | Snapshot signature mismatch (tampered) |
| `401502` | 400 | Malformed snapshot envelope |
| `401503` | 400 | Unknown or expired signing key id |
| `401504` | 400 | Unsupported snapshot schema version |
| `401505` | 403 | Snapshot tenant or store scope mismatch |
| `401506` | 400 | Snapshot of a finalized transaction cannot be operated on |
| `401507` | 503 | Snapshot generation failed. On the carried path the request fails and is safe to repeat; on the cache path the operation succeeds with a null snapshot |
| `401508` | 422 | Snapshot-less request under REQUIRED mode |
| `401509` | 413 | Decompressed request body over the ceiling |
| `401510` | - | Transaction sequence duplicate or gap detected (audit) |
| `401511` | 409 | The same `cart_id` was already finalized as a different transaction |
| `401512` | 400 | Carried snapshot addresses a different cart than the URL |
| `401513` | 409 | `transaction_no` matches more than one open session (`business_counter` required) |
| `401514` | 400 | Void is limited to the current business date and open session |

## Idempotency

Duplicate finalizes converge on `cart_id`.

- **cart**: before inserting, an existing tranlog is looked up by `cart_id`; a genuine retry of the same finalize returns it. A different operation reusing the id gets `409` (`401511`)
- **report / journal / stock**: first-wins skip on `cart_id`, so redelivery converges to one record
- **Database**: partial unique index on `cart_id` for `tran` and `stock_updates`

## Index migration

**The only trigger is the tenant creation API (`POST /api/v1/tenants`)** — it does not run at application startup. A new tenant goes through it on creation, but **an existing tenant is not migrated automatically**. Introducing this feature into a running deployment requires a separate way to run the migration over existing tenants.

The migration itself does the following.

1. Drop the stale unique index (the one without `business_counter`)
2. Create the new indexes
3. **Verify the end state and abort startup with `DatabaseException` if it was not reached**

A silently skipped step fails open — a stale unique index blocking finalize inserts, or a missing `cart_id` dedupe index — and looks healthy, so startup fails loudly instead.

For `status_tran`, a **data migration** runs before the new unique key is enforced: existing records take their epoch from the transaction they refer to. Matching them with "epoch or null" is not viable, because legacy `transaction_no` and `seq` are both 1-based and their ranges overlap completely, so a lookup for this session's `seq=1` would find the terminal's first-ever sale.

## Receipt numbering (issue #166)

The terminal carries **one running counter**, `receipt_counter` — the number of
transactions it has finalized — and the printed receipt number is derived from it:

```
receipt_no = RECEIPT_NO_START_VALUE + ((receipt_counter - 1) mod range_width)
```

Keeping the wrap in the derivation is what lets the open-time reconcile work. A
counter only ever increases, so `max(stored, carried)` is a valid comparison; a
printed number cycles, and `max(999999, 111111)` would undo a wrap permanently.

| Value | Owner | When it moves |
|---|---|---|
| `receipt_counter` | the terminal (durable home: terminal service) | once per finalized transaction |
| `receipt_no` | derived, not stored on the terminal | with the counter, wrapping inside the range |
| range (`RECEIPT_NO_START_VALUE` / `RECEIPT_NO_END_VALUE`) | master-data settings | when an operator changes it |

A client reads the range from master-data like any other terminal setting
(`GET /tenants/{tenant_id}/settings/{name}/value`) and receives the counter in
its terminal token (`receipt_counter` claim) at open. Tenant setup seeds
`RECEIPT_NO_START_VALUE` / `RECEIPT_NO_END_VALUE` with the shipped defaults so
that lookup always answers (#174) - a service falls back to its own
configuration when a setting is missing, but that fallback is invisible over
the API, and the client has to see the same range the backend numbers with. It sends its own high-water
counter back at the next open, where `max()` reconciles it — so a number used
during an offline session is never reissued.

**Invariant on the carried path**: `1 tranlog = 1 seq = 1 receipt_counter =
1 printed receipt_no`. Abandoning a cart consumes nothing.

A **cancellation is a finalize** and follows the same rule (#170): it writes a
transaction log and prints a receipt, so `POST /carts/{cart_id}/cancel` carries
the same finalize context `bill` does and consumes a number from the terminal's
series. Without it a cancelled sale would be numbered from the server-side
counters, whose `transaction_no` shares the `(business_counter, transaction_no)`
key space with the carried per-open `seq`.

**Gaps** are possible and permitted, but only from: a safe jump when a terminal
is replaced, an offline-finalized transaction that never arrived, a reconcile
or where the stored counter was higher. Nothing in normal operation produces one, so
a hole in `receipt_counter` is a signal worth investigating.

`receipt_counter` is recorded on the transaction log (non-unique index) because a
printed number cannot be ordered once the range wraps — `111115` says nothing
about which cycle it belonged to. It is **not** a transaction identity: dedupe on
`cart_id`.

Pre-#166 clients keep working: they carry no counter, send their number under the
old `receipt_no` name at open (numerically the same value — they counted 1, 2, 3
with no wrap), and their receipt numbers are recorded as sent.

## Rollback is accepted, and visible afterwards (#165)

The signature proves an envelope was issued unmodified. It does not prove it is
the **current** one, and on the stateless path the server deliberately does not
consult the cache, so it has no other basis for telling a current envelope from
an earlier one for the same cart. Refusing a stale envelope synchronously would
mean knowing the high-water mark per cart — a per-request write, which is exactly
what phase 2 removed.

So rollback is accepted and made findable instead. The cart document carries a
monotonic `revision`, covered by the signature, and every issued snapshot
advances it:

```
create → revision 1 → add item → revision 2 → add item → revision 3
```

The revision a request *presented* is recorded on its request log entry, as its
own `snapshot_info` field — not in the body, which the logging middleware strips
(#155):

```json
"snapshot_info": {"cart_id": "…", "revision": 3, "schema_version": 2, "kid": "v1"}
```

Normal operation is strictly increasing and a lost-ACK retry repeats a value.
A replayed older envelope is the one that goes **down**, which a query over
`snapshot_info.cart_id` ordered by `request_info.accept_time` finds directly
(there is an index for it).

The index is created by tenant setup, and nothing creates it at startup — so on
an environment that already has tenants, `POST /api/v1/tenants/{tenant_id}` has
to be re-run once per tenant before the query is indexed rather than a
collection scan. Index creation is idempotent, and this is the same step #156
needed for its own indexes.

Envelopes are issued at `schema_version` 2. Version 1 is still accepted: a client
that has not migrated presents one, and refusing it would break the failover the
snapshot exists for — such an envelope simply carries no revision to record.

Note the mechanics: the middleware that peels the envelope runs *outside* the
request logger, so by the time the request is logged the envelope is gone. The
peel leaves the scalars on the request scope for the logger to pick up.

Switching paths inside one cart used to be the case that got past this. The
carried path writes nothing, so a cart built up by carried requests left the
cache holding it as it was at creation, and one snapshot-less request continued
from there — dropping everything in between and answering with a correctly
signed snapshot of a cart missing it. The revision it presented afterwards would
go down, so it was *sometimes* visible; a client that stayed on the cache path
left no trace at all.

That is now impossible rather than detectable (#192). See below.

## One cart, one path (#192)

The path is chosen per request, on whether a snapshot came with it — so nothing
stopped one cart from using both. The client now says which way it will work
when it opens the cart:

```json
POST /carts   {"transactionType": 101, "carrySnapshot": true}
```

With `carrySnapshot: true` the cart is **never written to the cache** — not even
at creation, which is the one request that always wrote, because it has nothing
to carry yet and the server could not know what the client would do. There is
then no stale copy for a snapshot-less request to continue from, and it finds no
cart at all:

```
carrySnapshot=true    carried → 200      without a snapshot → 404 (401002)
carrySnapshot=false   carried → 409 (401515)   without a snapshot → 200
```

Both directions are refused, because both lose the same thing. Declaring the
cache path and then carrying leaves the cache copy behind while the cart moves
on, which is the same silent loss reached from the other side.

The declaration rides in the signed cart document, so checking it costs no cache
read: a snapshot states which way its cart was opened. A cart created before the
field existed says neither, and is left alone — carts in flight across the
deployment keep working.

`carrySnapshot` defaults to false, which is what a client that predates it means
by not sending it. In `CART_REQUEST_SNAPSHOT_MODE=REQUIRED` it is not needed:
every mutating request has to carry, so a cached copy could never be read and
none is written.

## Two numbering series while DUAL mode is on (#168)

The finalize path branches per **transaction**, not per terminal:

| request | numbers come from |
|---|---|
| carries a finalize context | the terminal's running `receipt_counter` |
| carries none | cart's own `terminal_counter` collection |

A phase 2 terminal whose snapshot signing has degraded is issued no snapshot, so
it cannot carry anything and its next sale is numbered from the *other* series.
That series knows nothing about how far the terminal has advanced, so it can
print a receipt number the terminal has already issued.

An unset or malformed key no longer reaches this point: the service refuses to
start without a usable one (#192). What remains is a key that loads and then
fails to sign, which lands here identically — so the detection stays.

This is **detected, not blocked**: refusing the finalize would stop a store
selling over a key misconfiguration, and the posture for numbering integrity here
is audit detection rather than enforcement (spec 156 Q58). A finalize that falls
into the server-side series while the terminal has one of its own logs at ERROR

```
Finalize numbered from the server-side series while the terminal has its own
(issue #168): cart_id=… reason=signing_degraded terminal_receipt_counter=…
```

and writes a `numbering_fallback` record to the restore audit trail
(`log_cart_restore`), with `reject_reason` naming which condition fired (`signing_degraded`,
`snapshot_without_finalize_context`, or `no_carried_context`).

One case is deliberately out of reach: a phase 2 terminal that has not numbered
anything yet, whose signing is healthy and which carries no snapshot at all,
looks exactly like a phase 1 terminal. Open seeds every terminal's counter with
zero, so treating zero as "has its own series" would report every legacy
finalize as an incident instead.

`CART_REQUEST_SNAPSHOT_MODE=REQUIRED` removes the window entirely — a
snapshot-less mutating request is rejected, so there is no second series to fall
into. Until then, a degraded signing key is an incident to fix, and now one that
is visible per transaction rather than only in the startup log.

## Signing is a requirement, not a feature (#192)

Once a cart can be held by the client alone, an unsigned response stops being a
missing extra and becomes a lost cart: the client is handed a `cart_id` that
addresses nothing, and the server kept no copy to find. So the situation is
removed rather than worked around.

**The service does not start without a usable signing key.** An unset key, a
malformed one, and one shorter than 32 bytes each stop the process at startup
instead of leaving it to answer requests it cannot serve correctly. The key
committed to this repository is refused the same way — it signs and verifies, so
every other signal looks healthy while the signature protects nothing — unless
`SNAPSHOT_ALLOW_INSECURE_KEY=true` says the stack really is a development one.

That leaves one case startup cannot see: a key that loads and then fails to sign.
A carried response that comes out without a snapshot is refused with **503
(`401507`)** rather than returned unsigned. Nothing is lost by refusing, and the
client recovers by repeating the request:

- a carried request writes no cart state, so a repeat with the snapshot the
  client still holds is simply the same request,
- a finalize does write, and is idempotent by `cart_id` (#170), so a repeat
  returns the transaction already recorded.

Repeat, do not start over. A finalize records the transaction and publishes it
before the response is built, so the sale exists even though the client was told
the request failed. Ringing it up again produces a new `cart_id`, and dedupe is
on `cart_id` - it would be booked a second time. The 503 is declared on every
route that can return it so a generated client sees this in the API contract and
not only here.

A cart the server holds in its cache is unaffected: its snapshot is a
convenience, the field goes out null, and the operation still succeeds.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SNAPSHOT_HMAC_KEYS` | unset | Snapshot signing keys. **Required — the service does not start without one** (#192), and refuses a key shorter than 32 bytes. See the key rotation runbook, [available in Japanese only](../../ja/cart-snapshot-key-rotation.md) |
| `SNAPSHOT_ALLOW_INSECURE_KEY` | `false` | Allows startup with the signing key committed to this repository. Local development only: that key signs and verifies, so anyone who can read the repository can mint a snapshot with any prices in it |
| `CART_REQUEST_SNAPSHOT_MODE` | `DUAL` | Migration mode (above) |
| `MAX_REQUEST_BODY_BYTES` | `4194304` | Request body ceiling, compressed or not. Also sizes the cart's own budget (below). Above the 1MB default every other service carries, because the carried cart document is cart's largest legitimate body (#195) |
| `REQUEST_DECOMPRESS_MAX_BYTES` | unset | Deprecated name for the above. Still honoured if set, and wins over the new name, so an existing deployment is not silently reset to the default |
| `REQUEST_LOG_STRIP_FIELDS` | `signedSnapshot,signed_snapshot` | Shared (commons) setting: body fields the request log replaces with a metadata marker, so the carried snapshot is not stored on every request (#155) |
| `REQUEST_LOG_MAX_BODY_BYTES` | `32768` | Shared (commons) setting: size ceiling for a logged body |

## The cart is bounded by what the client can send back

The snapshot is issued by the server and presented by the client on its next mutating request, so `MAX_REQUEST_BODY_BYTES` bounds it. The cart itself had no bound, so a large enough basket left the terminal holding an envelope it could not return: every following request answered `413`, and under `REQUIRED` the cart could be neither completed nor cancelled (#200).

A line item that would take the snapshot past **60% of `MAX_REQUEST_BODY_BYTES`** is refused with `409` (code `401516`) — measured on the snapshot that would actually be issued, not estimated from a line count, because what a line costs depends on the item masters carried with it. The refusal happens *before* anything is committed, so the cart is left exactly as it was and the basket can still be settled; the rest goes in another transaction.

A warning is logged at 80% of that budget, so the log says so before the till does.

At the 4 MB default that is roughly 2,800 line items of distinct SKUs, with the warning around 2,260. Measured: a 999-line transaction carries 894 KB, well inside it.

## Removed APIs

| Removed | Replacement |
|---|---|
| `POST /api/v1/carts/{cart_id}/restore` | Carry the snapshot on the operation itself; the cart is reconstructed, so there is nothing to restore first |
| `GET /api/v1/carts/{cart_id}` | The client holds the cart as its snapshot, so there is no need to read it back from the server |

DUAL mode keeps snapshot-less **mutating** requests working, but it does not bring these two endpoints back.

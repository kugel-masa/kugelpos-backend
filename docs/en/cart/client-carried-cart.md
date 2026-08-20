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
| Decompressed ceiling | `REQUEST_DECOMPRESS_MAX_BYTES` (default 1MB) |
| Over the ceiling | `413` (code `401509`). Enforced *during* expansion, so a small forged body cannot exhaust memory |
| Unsupported encoding | `415`, including chained values such as `gzip, br` |

Compression is optional; uncompressed requests behave as before. Measured, a 50-line cart is 50KB raw, 3.6KB gzipped, 2.9KB with brotli.

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
| `401507` | - | Snapshot generation failed (degraded; the operation itself succeeds) |
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

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SNAPSHOT_HMAC_KEYS` | unset | Snapshot signing keys. **Unset means degraded**: no snapshot is issued, every carried one is rejected, and clients silently fall back to the cache path. See the key rotation runbook, [available in Japanese only](../../ja/cart-snapshot-key-rotation.md) |
| `CART_REQUEST_SNAPSHOT_MODE` | `DUAL` | Migration mode (above) |
| `REQUEST_DECOMPRESS_MAX_BYTES` | `1048576` | Decompressed request body ceiling |
| `SNAPSHOT_SIZE_WARN_BYTES` | `262144` | Snapshot size warning threshold |
| `REQUEST_LOG_STRIP_FIELDS` | `signedSnapshot,signed_snapshot` | Shared (commons) setting: body fields the request log replaces with a metadata marker, so the carried snapshot is not stored on every request (#155) |
| `REQUEST_LOG_MAX_BODY_BYTES` | `32768` | Shared (commons) setting: size ceiling for a logged body |

## Removed APIs

| Removed | Replacement |
|---|---|
| `POST /api/v1/carts/{cart_id}/restore` | Carry the snapshot on the operation itself; the cart is reconstructed, so there is nothing to restore first |
| `GET /api/v1/carts/{cart_id}` | The client holds the cart as its snapshot, so there is no need to read it back from the server |

DUAL mode keeps snapshot-less **mutating** requests working, but it does not bring these two endpoints back.

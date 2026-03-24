# Upstream Changes Proposal — Kugelpos Backend

**Date**: 2026-03-24
**Author**: masa@kugel
**Purpose**: Decision material for fork maintainers on whether to adopt recent upstream changes
**Target audience**: Project members of the forked repository

---

## Executive Summary

Three feature sets have been developed on the upstream repository since the last sync point. This document provides an objective evaluation of each to help you decide which to adopt, defer, or skip.

| Change Set | Type | Risk | Effort to Adopt | Recommendation |
|-----------|------|------|----------------|----------------|
| **Category Promotion** (#58+#64) | New Feature | Low | Medium | Adopt if promotions are planned |
| **Unit Test Coverage** (#62) | Quality | Very Low | Low | **Strongly recommend** |
| **Terminal JWT Auth** (#67) | Architecture | Medium | High | **Strongly recommend** |

---

## 1. Category-Based Promotion System

**Issues**: #58 (feature) + #64 (bugfix)
**PRs**: #59, #65, #66
**Status**: Merged
**Scale**: +8,321 / -66 lines, 54 files across 4 services

### What It Does

Adds an automatic percentage-discount system based on product category codes. When an item is added to the cart, the system checks if any active promotions match the item's category and applies the best discount rate.

```
Customer buys item in category "CAT01"
  → Promotion "10% off all CAT01 items" is active
  → Discount automatically applied at subtotal
```

### Architecture

- **Plugin-based**: Implemented as a `sales_promo_strategy` plugin — no core cart logic modified
- **Self-contained**: Plugin creates its own repository via `configure()`, following Open/Closed Principle
- **Multi-service**: Spans commons, master-data (CRUD), cart (plugin), report (aggregation)

### Services Affected

| Service | Change | Impact |
|---------|--------|--------|
| commons | `DiscountInfo` model extension | Low — additive field |
| master-data | Promotion CRUD API (new endpoints) | None to existing endpoints |
| cart | `CategoryPromoPlugin` loaded via `plugins.json` | None to existing cart logic |
| report | `PromotionReportPlugin` for aggregation | None to existing reports |

### Adoption Considerations

| Factor | Assessment |
|--------|-----------|
| **Breaking changes** | None. Plugin architecture means no existing code is modified |
| **Merge conflicts** | Low risk. New files + minor model extensions |
| **Can be deferred** | Yes. If promotions are not in your roadmap, this can be skipped entirely |
| **Dependencies** | None. Self-contained feature |
| **Test coverage** | Integration tests included. #64 fixes a redundant calculation bug |

### Recommendation

**Adopt if category promotions are in your roadmap.** Skip if not — the plugin architecture ensures zero impact on existing functionality either way. The #64 bugfix is only relevant if #58 is adopted.

---

## 2. Unit Test Coverage Improvement

**Issue**: #62
**PR**: #63
**Status**: Merged
**Scale**: +24,071 / -28 lines, 80 files across all 7 services

### What It Does

Adds comprehensive unit tests using `AsyncMock`/`MagicMock` for repository dependencies. Tests run without any running services (no Docker, no MongoDB, no Dapr required).

### Coverage Before → After

| Service | Before | After | Key Areas Covered |
|---------|--------|-------|-------------------|
| account | 0% | ~50% | Auth logic, token validation |
| terminal | 5% | ~55% | Terminal/tenant service logic |
| master-data | 18% | ~60% | Promotion, item, category, payment services |
| cart | 29% | ~65% | State machine edge cases, CategoryPromoPlugin |
| journal | 33% | ~70% | Log service branching, journal CRUD |
| stock | 20% | ~55% | Stock API, snapshot, alerts |
| report | 54% | ~75% | Schema transformers, report endpoints |

### Adoption Considerations

| Factor | Assessment |
|--------|-----------|
| **Breaking changes** | None. Test files only — no production code modified |
| **Merge conflicts** | Very low. Tests are new files in `tests/` directories |
| **Can be deferred** | Not recommended. Tests protect against regressions in future changes |
| **Dependencies** | Partial dependency on #58 (CategoryPromoPlugin tests). Can be cherry-picked without |
| **Maintenance cost** | Low. Tests use standard pytest + mock patterns |

### Recommendation

**Strongly recommend adopting.** This is the lowest-risk, highest-value change set. Even if you skip #58 and #67, these tests will protect your existing codebase. Cherry-pick individual service test files if full adoption is not desired.

---

## 3. Terminal JWT Authentication

**Issue**: #67
**PR**: #68
**Status**: Open (pending review)
**Scale**: +5,322 / -68 lines, 73 files across all services + commons

### What It Does

Replaces per-request API key verification (HTTP call to terminal service on every request) with JWT token-based authentication. Tokens are issued at terminal lifecycle events and verified locally by each service.

### Architecture Change

```
BEFORE (every request):
  POS → [X-API-KEY] → Cart → [HTTP] → Terminal Service → DB lookup → response
                            ↑ 50-100ms overhead per request

AFTER (JWT):
  POS → [JWT] → Cart → Local verification (< 1ms) → response
  JWT re-issued only at: open / sign-in / sign-out / close
```

### Performance Impact

Measured with Locust load tests (10 concurrent users, 2 minutes) on production configuration (gRPC + multi-worker):

| Metric | API Key Auth | JWT Auth | Improvement |
|--------|:-----------:|:-------:|:----------:|
| **Average response time** | 114ms | 36ms | **-68%** |
| **P95 response time** | 200ms | 98ms | **-51%** |
| **Add Item (avg)** | 101ms | 30ms | **-70%** |
| **Add Item (P95)** | 200ms | 96ms | **-52%** |

### Services Affected

| Service | Change Type | Description |
|---------|------------|-------------|
| **commons** | Core change | JWT generation, verification, claims-to-model conversion, auth priority logic |
| **terminal** | New endpoint + modification | `POST /auth/token`, X-New-Token header on lifecycle APIs |
| **cart** | Significant modification | JWT-based dependency injection, 6 web repositories modified for JWT forwarding |
| **report** | Minor modification | `get_requesting_staff_id` extracts staff_id from JWT claims |
| **master-data, journal, stock** | No code change | Automatically supported via `__get_tenant_id()` modification in commons |

### Key Design Decisions

1. **Backward compatible**: API key auth continues to work. Auth priority: Terminal JWT → User JWT → API Key
2. **No token revocation**: Tokens expire after 24h. Key rotation invalidates all tokens
3. **Lifecycle re-issuance**: JWT is refreshed at state changes via `X-New-Token` response header
4. **`jwt_token` on model**: Transport field added to `TerminalInfoDocument` with `Field(exclude=True)` to prevent DB persistence

### Adoption Considerations

| Factor | Assessment |
|--------|-----------|
| **Breaking changes** | None for API consumers. Full backward compatibility maintained |
| **Merge conflicts** | Medium risk. `security.py`, `terminal.py`, and cart dependencies are heavily modified |
| **Can be deferred** | Yes, but performance penalty continues. Most impactful under high load |
| **Dependencies** | Requires #62 (unit tests) for full test coverage. Can work without #58 |
| **Migration effort** | Client-side change needed: POS terminals must call `POST /auth/token` and store JWT. Existing API key flow continues working during migration |
| **Rollback plan** | Remove JWT code paths. API key auth remains fully functional as fallback |

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Shared SECRET_KEY compromise affects both user and terminal tokens | High | Monitor for anomalies; plan key rotation as future work |
| JWT claims become stale between lifecycle events | Medium | 24h expiry limits staleness; lifecycle re-issuance covers most state changes |
| Client fails to store X-New-Token | Low | Falls back to API key or stale JWT; backward compatibility ensures continued operation |

### Recommendation

**Strongly recommend adopting.** The 68% response time improvement is significant, especially for high-traffic POS operations. The backward-compatible design means zero client-side breakage during migration. The main adoption cost is merge conflict resolution in `security.py` and cart dependencies.

---

## Adoption Order

If adopting all three, the recommended order is:

```
1. #62 (Unit Tests)     ← No risk, immediate value
2. #58+#64 (Promotions) ← Independent feature, low conflict
3. #67 (JWT Auth)       ← Largest change, benefits from #62 tests being in place
```

If adopting selectively:

- **Minimum**: #62 only (test coverage)
- **Performance-focused**: #62 + #67 (tests + JWT auth)
- **Feature-focused**: #62 + #58+#64 (tests + promotions)

---

## Technical Contact

For questions about implementation details, merge strategy, or migration planning:
- GitHub: @kugel-masa
- Issues: https://github.com/kugel-masa/kugelpos-backend/issues

# Feature Specification: Lifecycle-Aware JWT Token Authentication for Terminal API Key

**Feature Branch**: `feature/67-terminal-jwt-auth`
**Created**: 2026-03-23
**Status**: Draft
**Input**: Replace per-request API key verification (HTTP calls to terminal service) with JWT token-based authentication. Tokens issued at terminal lifecycle state changes, enabling local verification at each service without inter-service calls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initial Token Acquisition (Priority: P1)

A POS terminal authenticates with its API key and receives a JWT token for subsequent requests. This eliminates the need for every service to call the terminal service for API key validation on each request.

**Why this priority**: This is the foundation of the entire feature. Without token issuance, no other functionality works.

**Independent Test**: Can be fully tested by sending a POST request with a valid API key to the token endpoint and verifying a valid JWT is returned with correct claims.

**Acceptance Scenarios**:

1. **Given** a registered terminal with a valid API key, **When** the terminal sends POST /auth/token with X-API-KEY header, **Then** the system returns a JWT containing tenant_id, store_code, terminal_no, terminal_id, status, and expiry claims.
2. **Given** an invalid or unknown API key, **When** the terminal sends POST /auth/token, **Then** the system returns 401 Unauthorized.
3. **Given** a valid API key for a terminal that has not been opened, **When** the terminal sends POST /auth/token, **Then** the JWT is issued with status reflecting the current terminal state and no staff claims.

---

### User Story 2 - Local JWT Verification at Services (Priority: P1)

Each service (cart, master-data, report, journal, stock) can verify the terminal JWT locally without making inter-service HTTP calls. The JWT claims provide all necessary context (tenant_id, store_code, staff info, etc.).

**Why this priority**: This delivers the core performance benefit — eliminating inter-service authentication calls.

**Independent Test**: Can be tested by sending a request with a valid terminal JWT to any service endpoint and verifying the service extracts tenant_id and other claims locally without calling the terminal service.

**Acceptance Scenarios**:

1. **Given** a valid terminal JWT, **When** a service receives a request with the JWT in the Authorization header, **Then** the service verifies the token locally and extracts tenant_id, store_code, and other claims.
2. **Given** an expired terminal JWT, **When** a service receives a request, **Then** the service returns 401 Unauthorized.
3. **Given** a terminal JWT with an invalid signature, **When** a service receives a request, **Then** the service returns 401 Unauthorized.

---

### User Story 3 - Token Re-issuance on Lifecycle State Changes (Priority: P1)

When a terminal undergoes a lifecycle state change (open, sign-in, sign-out, close), the terminal service issues a new JWT reflecting the updated state. The new token is delivered via a response header so the client can use it for subsequent requests.

**Why this priority**: Ensures JWT claims stay current with terminal state (staff, business_date, counters) without requiring explicit refresh calls.

**Independent Test**: Can be tested by performing a terminal open operation and verifying the response includes a new JWT in the X-New-Token header with updated business_date, open_counter, and status claims.

**Acceptance Scenarios**:

1. **Given** a terminal with a valid JWT, **When** the terminal opens (POST /terminals/{id}/open), **Then** the response includes X-New-Token header with a JWT containing updated business_date, open_counter, business_counter, and status="Opened".
2. **Given** an opened terminal, **When** a staff member signs in (POST /terminals/{id}/sign-in), **Then** the response includes X-New-Token with staff_id and staff_name claims added.
3. **Given** a signed-in terminal, **When** the staff member signs out (POST /terminals/{id}/sign-out), **Then** the response includes X-New-Token with staff_id and staff_name claims removed.
4. **Given** an opened terminal, **When** the terminal closes (POST /terminals/{id}/close), **Then** the response includes X-New-Token with status="Closed".

---

### User Story 4 - Backward Compatibility During Migration (Priority: P2)

During the migration period, all services continue to accept the existing X-API-KEY authentication alongside the new JWT authentication. This allows POS terminals to be upgraded incrementally.

**Why this priority**: Enables gradual rollout without breaking existing terminals that have not yet been updated.

**Independent Test**: Can be tested by sending requests with X-API-KEY (old method) to any service and verifying they still work as before.

**Acceptance Scenarios**:

1. **Given** a service that supports both auth methods, **When** a request arrives with X-API-KEY header (no JWT), **Then** the service authenticates using the existing API key flow.
2. **Given** a service that supports both auth methods, **When** a request arrives with a terminal JWT in the Authorization header, **Then** the service authenticates using local JWT verification.
3. **Given** a request with both X-API-KEY and a terminal JWT, **When** the service processes authentication, **Then** the JWT takes precedence.

---

### User Story 5 - Cart Service Uses JWT Claims Instead of Terminal Info Fetch (Priority: P2)

The cart service extracts terminal context (tenant_id, store_code, staff info) from JWT claims instead of fetching terminal_info from the terminal service. The cart forwards the JWT when calling master-data service.

**Why this priority**: Removes the largest source of inter-service auth traffic (cart → terminal service calls and terminal info caching).

**Independent Test**: Can be tested by sending a cart operation request with a terminal JWT and verifying no HTTP call is made to the terminal service for authentication.

**Acceptance Scenarios**:

1. **Given** a cart request with a terminal JWT, **When** the cart processes the request, **Then** tenant_id, store_code, terminal_no, and staff info are extracted from JWT claims without calling the terminal service.
2. **Given** a cart request requiring master-data lookup, **When** the cart calls master-data, **Then** the terminal JWT is forwarded in the Authorization header instead of passing an API key.

---

### Edge Cases

- What happens when a terminal's JWT expires mid-transaction? The terminal re-authenticates with its API key to obtain a new token.
- What happens if the signing key is rotated? Tokens signed with the old key will fail verification; terminals must re-authenticate.
- What happens when a terminal sends a user JWT (account service JWT) instead of a terminal JWT to a terminal-authenticated endpoint? The service distinguishes by checking the token_type claim and rejects mismatched token types.
- What happens when the terminal service is unavailable? Existing JWTs continue to work for local verification until expiry. Only initial token acquisition and state-change re-issuance are affected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a POST /auth/token endpoint in the terminal service that accepts X-API-KEY and returns a signed JWT.
- **FR-002**: System MUST include the following claims in the terminal JWT: tenant_id, store_code, terminal_no, terminal_id, staff_id, staff_name, business_date, open_counter, business_counter, status, iss ("terminal-service"), token_type ("terminal"), iat, exp.
- **FR-003**: System MUST re-issue a new JWT on terminal lifecycle state changes (open, sign-in, sign-out, close) via the X-New-Token response header.
- **FR-004**: System MUST set JWT expiry to 24 hours by default, configurable via settings.
- **FR-005**: System MUST provide a terminal JWT verification function in kugel_common/security.py that validates signature, expiry, and token_type.
- **FR-006**: All services (cart, master-data, report, journal, stock) MUST accept terminal JWT as an authentication method.
- **FR-007**: System MUST maintain backward compatibility with existing X-API-KEY authentication during migration.
- **FR-008**: Cart service MUST extract terminal context from JWT claims instead of fetching terminal_info from the terminal service when a JWT is provided.
- **FR-009**: Cart service MUST forward the terminal JWT to master-data service instead of passing API key when a JWT is available.
- **FR-010**: System MUST use the existing shared SECRET_KEY (from settings_auth.py) for JWT signing and verification.
- **FR-011**: System MUST distinguish terminal JWTs from account (user) JWTs using the token_type claim.
- **FR-012**: Existing OAuth2 user JWT authentication and PUBSUB_NOTIFY_API_KEY authentication MUST remain unchanged.

### Key Entities

- **Terminal JWT Token**: A signed JWT containing terminal identity and state claims. Issued by the terminal service. Verified locally by all services. Distinguished from user JWTs by token_type="terminal".
- **JWT Claims**: The payload embedded in the terminal JWT. Reflects the current terminal state including tenant context, staff assignment, business date, and lifecycle counters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Authentication for terminal requests completes without inter-service HTTP calls when using JWT (local verification only).
- **SC-002**: All existing terminal-authenticated API endpoints continue to function with X-API-KEY authentication (zero breaking changes).
- **SC-003**: Terminal lifecycle operations (open, sign-in, sign-out, close) return a refreshed JWT reflecting the updated state.
- **SC-004**: All existing tests pass after the changes, and new tests cover JWT issuance, verification, re-issuance, and expiry scenarios.
- **SC-005**: Cart service no longer makes HTTP calls to the terminal service for authentication when a valid JWT is provided.

## Assumptions

1. **Shared signing key**: The existing SECRET_KEY in settings_auth.py is used for both user JWTs and terminal JWTs. The token_type claim distinguishes them.
2. **Token delivery**: New tokens from lifecycle operations are delivered via X-New-Token response header. The POS terminal client is responsible for storing and using the new token.
3. **No token revocation**: Individual token revocation is not implemented. Tokens are valid until expiry. Key rotation handles bulk invalidation if needed.
4. **24-hour default expiry**: Sufficient for a typical business day. Terminals re-authenticate via API key if the token expires.
5. **Staff claims optional**: staff_id and staff_name are only present in the JWT after sign-in and removed after sign-out.
6. **Pub/sub notifications unchanged**: Internal pub/sub communication continues to use service tokens or PUBSUB_NOTIFY_API_KEY.

## Out of Scope

- Token revocation or blacklisting
- Refresh token mechanism (re-authentication uses API key)
- JWT key rotation automation
- Removal of API key authentication (retained for backward compatibility)
- Changes to account service user JWT authentication
- Changes to pub/sub notification authentication

## Dependencies

- Existing JWT infrastructure (python-jose, SECRET_KEY, settings_auth.py) in kugel_common
- Terminal service lifecycle endpoints (open, sign-in, sign-out, close)
- All consumer services (cart, master-data, report, journal, stock) authentication dependencies
- Cart service terminal_cache_dependency.py (to be deprecated/bypassed when JWT is available)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shared signing key compromise affects both user and terminal tokens | High - both auth systems compromised | Monitor for anomalies; key rotation plan as future work |
| JWT claims become stale between lifecycle events | Medium - decisions made on outdated state | 24-hour expiry limits staleness; lifecycle re-issuance covers most state changes |
| Client fails to store/use new token from X-New-Token header | Medium - falls back to old token or API key | Clear client documentation; backward compatibility ensures continued operation |
| Migration period complexity with dual auth support | Low - additional code paths to maintain | Clean separation of auth methods; feature flag for future API key deprecation |

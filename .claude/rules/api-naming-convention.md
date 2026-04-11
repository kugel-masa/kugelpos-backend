# API Naming Convention (v2)

This rule defines the naming conventions for v2 API endpoints.
v1 endpoints remain unchanged for backward compatibility with external clients.

## Resource Names

- Use **plural forms** for countable resources: `/items`, `/carts`, `/terminals`, `/payments`
- **Collective nouns** remain as-is: `/staff`, `/stock`

## Path Segment Formatting

- **Compound words** (two or more separate words): hyphen-separated
  - Examples: `/item-books`, `/sign-in`, `/sign-out`, `/cash-in`, `/cash-out`, `/delivery-status`, `/snapshot-schedule`, `/reorder-alerts`, `/resume-item-entry`
- **Compound nouns** (single concept): lowercase concatenation
  - Examples: `/lineitems`, `/unitprice`

## Path Parameters

- Always use **snake_case**
  - Examples: `{tenant_id}`, `{store_code}`, `{item_code}`, `{terminal_no}`, `{transaction_no}`, `{line_no}`, `{category_no}`, `{tab_no}`

## HTTP Methods and Redundant Paths

- Use HTTP methods to express CRUD operations; do NOT include the verb in the path
  - `PUT /stock/{item_code}` (not `PUT /stock/{item_code}/update`)
- Use `POST` for action-oriented operations
  - `POST /carts/{cart_id}/cancel`
  - `POST /transactions/{transaction_no}/void`

## Summary Table

| Item | Rule | Example |
|------|------|---------|
| Resource name | Plural (collective nouns as-is) | `/items`, `/staff`, `/stock` |
| Path separator | Hyphen | `/item-books`, `/sign-in` |
| Compound noun | Lowercase concat | `/lineitems`, `/unitprice` |
| Redundant verb | Remove | `PUT ...` not `PUT .../update` |
| Path parameter | snake_case | `{line_no}`, `{category_no}` |
| Action operation | POST | `POST .../cancel` |

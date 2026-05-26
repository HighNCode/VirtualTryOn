# Orders Scope Rationale (`read_orders` without `read_all_orders`)

## Decision

- Keep app scopes without `read_all_orders`.
- Limit analytics commerce attribution to recent orders only.

## Enforcement

- Backend order ingestion clips lookback to maximum 60 days.
- Shopify GraphQL `orders` query applies `created_at` lower bound.

## Why this is compliant

- The app does not intentionally access historical orders beyond Shopify's default recent-order window.
- No feature depends on long-tail historical order retrieval.


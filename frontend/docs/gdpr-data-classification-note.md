# GDPR Data Classification Note (Internal)

Last updated: `2026-05-26`

## Purpose

This note documents data classes relevant to Shopify GDPR webhooks and how each class is handled by:
- `customers/data_request`
- `customers/redact`
- `shop/redact`

## Data Classification

### 1) Direct merchant account data
- Tables/areas: `stores` metadata (shop domain, email, store_name, billing fields).
- Classification: merchant/business data (not shopper personal profile records).
- Handling:
  - `customers/*`: not applicable.
  - `shop/redact`: hard deleted.

### 2) Shopper interaction/session data
- Tables/areas: sessions, analytics events, try-on workflow states.
- Classification: pseudonymous operational telemetry/session data.
- Handling:
  - `customers/*`: no direct customer-profile keyed export path.
  - `shop/redact`: hard deleted.

### 3) Measurement / image artifacts
- Tables/areas: measurement records, try-on artifacts, cache/media objects.
- Classification: sensitive pseudonymous biometric-adjacent data.
- Handling:
  - TTL/retention and policy controls apply during normal operation.
  - `customers/*`: no direct customer-profile keyed export path.
  - `shop/redact`: hard deleted via store data deletion workflow.

### 4) Webhook delivery logs
- Tables/areas: webhook deduplication records.
- Classification: operational metadata.
- Handling:
  - `customers/*`: not applicable.
  - `shop/redact`: deleted with store.

## Current Webhook Policy Statement

- `customers/data_request`: returns policy-consistent "no personal customer profile records stored for this webhook scope" response.
- `customers/redact`: acknowledges redaction request under same policy.
- `shop/redact`: authoritative full deletion path for shop-owned data.

## Follow-up Trigger

If future product work stores direct customer-identifiable profile fields (e.g., email, customer_id-bound profile records), add a dedicated customer-scoped export/redaction implementation before App Store submission updates.


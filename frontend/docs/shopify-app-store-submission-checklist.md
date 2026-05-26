# Shopify App Store Submission Checklist (May 2026)

## Blocking Compliance

- [ ] `2.2.4 GraphQL Admin API`: verify no non-theme REST Admin endpoints remain for business flows.
- [ ] `3.2.1 Orders scope`: analytics order lookup is capped to last 60 days; `read_all_orders` is not requested.

## Billing Compliance

- [ ] `1.2.2 Billing API`: `/billing/activate` verifies subscription status from Shopify before DB activation.
- [ ] Declined/cancelled billing return shows in-app error and does not activate plan.
- [ ] Reinstall path syncs billing status before merchants continue billing actions.
- [ ] In-app plan switching (upgrade/downgrade) works without reinstall/support contact.

## Theme Extension Compliance

- [ ] `5.1.1`: app is theme app extension first; `write_script_tags` scope removed.
- [ ] Onboarding/theme setup explicitly states theme app extension required.
- [ ] Migration note for legacy script-tag users is published.

## Data/UX Compliance

- [ ] `1.1.9`: widget add-to-cart sends only selected variant (`id`, `quantity`) with no hidden fees.
- [ ] `2.2.7`: no App Bridge ResourcePicker max modal auto-launch on page load.
- [ ] `5.1.5`: merchant-facing analytics are aggregate only; no per-customer measurement drill-down.

## TLS Evidence

- [ ] Backend production endpoint serves valid HTTPS certificate chain.
- [ ] Certificate validation output captured for submission packet.


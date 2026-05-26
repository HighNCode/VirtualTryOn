# Storefront Widget Release Runbook

This runbook is for customer storefront widget releases only.

## Scope

- Widget source of truth: `extensions/storefront-widget`.
- Merchant UI (`web`) is not part of this runbook.

## Pre-release

1. Edit storefront widget code only under:
   - `extensions/storefront-widget/assets`
   - `extensions/storefront-widget/blocks`
2. Bump widget version:
   - `npm run widget:version:bump`
3. Confirm file sync:
   - `npm run widget:version:sync`
4. Commit the version bump with widget changes.

## Deploy

1. Deploy extension:
   - `npm run widget:deploy`
2. In Shopify Admin, verify latest extension version is active on the target theme.

## Verify

1. Verify live storefront marker + asset cache token + runtime build marker:
   - `npm run widget:verify -- --url "https://<shop-domain>/products/<handle>"`
2. Run compliance guardrails:
   - `npm run compliance:guard`
3. Confirm full customer flow:
   - session starts
   - Step 1 consent gate works
   - measurement extract works
   - try-on generation works
   - add-to-cart works

## Guardrails

- CI guard: `.github/workflows/widget-version-guard.yml`
- Local guard command:
  - `npm run widget:guard -- --base origin/main`

The guard enforces:
- If widget assets/blocks change, `widget-release.json` version must also change.
- JS/Liquid version markers must stay synced with `widget-release.json`.

## Release Notes

Use template: `docs/widget-release-checklist-template.md`.

## Shopify Submission Artifacts

- `docs/shopify-app-store-submission-checklist.md`
- `docs/shopify-review-packet.md`
- `docs/script-tag-deprecation-migration.md`
- `docs/max-modal-compliance-note.md`
- `docs/tls-verification-checklist.md`

# Frontend Deployment Split

This repository has two independent frontend deployment surfaces:

- `web` (merchant onboarding/dashboard/settings): deployed via Vercel.
- `extensions/storefront-widget` (customer storefront widget): deployed via Shopify extension deploy.

## Source Of Truth

- Storefront widget production source: `extensions/storefront-widget`.
- Do not ship storefront widget behavior from `web`.

## Widget Release Commands

Run these commands from `frontend`:

```bash
npm run widget:version:bump
npm run widget:deploy
npm run widget:verify -- --url "https://<shop-domain>/products/<handle>"
```

Or run the combined release flow:

```bash
npm run widget:release
```

Detailed runbook: `docs/storefront-widget-release.md`.

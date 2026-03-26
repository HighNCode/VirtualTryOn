# Optimo Virtual Try-On (Shopify Plugin)

This repository contains:

- `extensions/*`: Shopify app extensions (CLI-managed)
- `web`: Next.js embedded app frontend, including Shopify-native GraphQL billing

The `web` app is discovered through `web/shopify.web.toml`, and Shopify CLI boots it as the app web process.

## Install

```bash
npm install
```

## Run Shopify plugin

```bash
npm run dev
```

This now allows `shopify app dev` to boot the `web` workspace as the app's web process.
Use the preview/install link printed by Shopify CLI to open the app from your dev store.

## Run frontend only

```bash
npm run dev:web
```

Frontend app will run from the `web` workspace.

## Environment

Create `web/.env.local` from `web/.env.example`:

```bash
API_BASE_URL=https://your-backend.example.com
NEXT_PUBLIC_SHOPIFY_API_KEY=your-shopify-app-client-id
NEXT_PUBLIC_DEFAULT_PRODUCT_GID=gid://shopify/Product/1234567890
NEXT_PUBLIC_DEFAULT_PRODUCT_IMAGE_URL=https://cdn.shopify.com/...
SHOPIFY_API_SECRET=your-shopify-app-client-secret
SHOPIFY_BILLING_TEST_MODE=false
```

The frontend now talks to the backend only through the local `/api/backend/*` proxy.
Keep `API_BASE_URL` server-side so the real backend origin is never shipped in the browser bundle.
`X-Shopify-Shop-Domain` is sent on requests so backend routers can bind to the active Shopify store in embedded context.
Shopify billing now runs through the GraphQL Admin API from inside the embedded app, with plan configuration served by the Next app.

## Billing setup

1. Configure your real app domain in [shopify.app.toml](/c:/Users/Mubashir/Desktop/Optimo VTS AI/optimo-virtual-try-on/shopify.app.toml) before public launch.
2. Run `shopify app deploy` after changing billing/webhook config so Shopify registers Direct API access and webhook subscriptions for production.
3. Set `SHOPIFY_BILLING_PLANS_JSON` if your live pricing differs from the default plans in the repo.
4. Keep `SHOPIFY_BILLING_TEST_MODE=false` in production. Set it to `true` only for billing QA on development stores.
5. If your external backend needs subscription or uninstall events, set `SHOPIFY_WEBHOOK_FORWARD_URL` so verified Shopify webhooks are forwarded after HMAC validation.

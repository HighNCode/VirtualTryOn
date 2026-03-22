# Optimo VTS Frontend (Web Workspace)

This is the Next.js web workspace for the embedded Optimo VTS Shopify app.

## Run

From repository root:

```bash
npm run dev
```

This starts Shopify CLI and lets it discover this workspace through `web/shopify.web.toml`.

To run only the Next.js app without Shopify CLI:

```bash
npm run dev:web
```

Or directly inside `web`:

```bash
npm run dev
```

## Environment

Create `.env.local` in `web` using `.env.example`:

```bash
API_BASE_URL=https://your-backend.example.com
NEXT_PUBLIC_SHOPIFY_API_KEY=your-shopify-app-client-id
NEXT_PUBLIC_DEFAULT_PRODUCT_GID=gid://shopify/Product/1234567890
NEXT_PUBLIC_DEFAULT_PRODUCT_IMAGE_URL=https://cdn.shopify.com/...
SHOPIFY_API_SECRET=your-shopify-app-client-secret
SHOPIFY_BILLING_TEST_MODE=false
```

When the app is opened from Shopify Admin, the frontend calls the upstream API only through the local `/api/backend/*` proxy so App Bridge can attach a session token without browser CORS issues.
Keep `API_BASE_URL` server-side. The browser bundle should never contain the real backend host or an internal store UUID.
Billing plan selection and billing-status reads use Shopify Direct API access from the embedded app via `shopify:admin/api/.../graphql.json`.

## Billing and webhooks

- Plan configuration is served from `web/app/api/shopify/billing/plans/route.ts` and can be overridden with `SHOPIFY_BILLING_PLANS_JSON`.
- Shopify webhook requests are verified in `web/app/api/webhooks/route.ts`.
- If `SHOPIFY_WEBHOOK_FORWARD_URL` is configured, verified webhook payloads are forwarded to that backend endpoint.
- Deploy `shopify.app.toml` with `shopify app deploy` after changing webhook or Direct API settings.

## Shopify CLI

This workspace is registered as the app's web process in `web/shopify.web.toml`.
Shopify CLI will start `npm run dev` in this directory when you run `shopify app dev` from the repository root.

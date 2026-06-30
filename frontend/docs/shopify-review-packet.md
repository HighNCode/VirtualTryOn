# Shopify App Store Review Packet (Optimo VTS Dev)

Last updated: `2026-05-26`

## 1) Compliance Summary

- Admin API migration: orders analytics uses GraphQL (no non-theme REST orders usage).
- Orders access guardrail: lookback hard-capped to 60 days; `read_all_orders` is not requested.
- Billing flow: approve/decline/cancel callback handling, verified activation path, plan change support.
- Storefront integration: Theme App Extension + App Proxy path, ScriptTag path deprecated and removed from runtime.

Supporting docs:
- [Submission checklist](./shopify-app-store-submission-checklist.md)
- [Orders scope rationale](./orders-scope-rationale.md)
- [ScriptTag deprecation note](./script-tag-deprecation-migration.md)
- [Max modal compliance note](./max-modal-compliance-note.md)
- [TLS verification checklist](./tls-verification-checklist.md)
- [GDPR data classification note](./gdpr-data-classification-note.md)

## 2) Architecture Snippet (Reviewer-Facing)

```text
Shopper (Product Page)
  -> Theme App Extension block (optimo_vts_widget.liquid)
  -> Shopify App Proxy (/apps/optimo-vts/*)
  -> Frontend proxy route (/widget-proxy/*)
  -> Backend API (/api/v1/*)
```

Clarification:
- Widget delivery is via Theme App Extension and app proxy.
- ScriptTag injection is not used by runtime flows.

## 3) Verification Evidence Checklist

### Billing Flows

- [ ] Approve subscription -> activation succeeds
  - Screenshot path:
  - Notes:
- [ ] Decline/cancel subscription -> clear error, no activation
  - Screenshot path:
  - Notes:
- [ ] Retry after decline -> successful approval path
  - Screenshot path:
  - Notes:
- [ ] Reinstall + resubscribe deterministic behavior
  - Screenshot path:
  - Notes:

### Theme Extension Path

- [ ] Add block via Theme Editor -> detection succeeds
  - Screenshot path:
  - Notes:
- [ ] Theme setup recheck screen confirms status
  - Screenshot path:
  - Notes:

### Cart/Add-to-Cart Behavior

- [ ] Add-to-cart payload contains only selected variant + quantity
  - Screenshot path:
  - Notes:

### Checkout-Only Assurance

- [ ] Redirect audit confirms no offsite payment/checkout URL construction in storefront/customer flows.
  - Search command output path:
  - Notes:
- [ ] All buyer checkout progression remains within Shopify cart/checkout.
  - Screenshot path:
  - Notes:

Command used:

```bash
rg -n "https?://.*(checkout|payment|pay)" frontend/web frontend/extensions/storefront-widget/assets/optimo-vts-widget.js -S
```

Captured output:

```text
[no matches]
```

## 4) TLS / SSL Runtime Evidence (Production)

Execution date (UTC): `2026-05-26`
Backend host: `optimo-virtual-try-on-rose.vercel.app`

Command used:

```bash
openssl s_client -connect <backend-domain>:443 -servername <backend-domain> -showcerts
```

PowerShell/Python fallback command used in this environment:

```bash
python -c "import ssl,socket;h='optimo-virtual-try-on-rose.vercel.app';ctx=ssl.create_default_context();s=ctx.wrap_socket(socket.socket(),server_hostname=h);s.connect((h,443));print(s.getpeercert());s.close()"
```

Capture fields:
- Certificate SAN/hostname match: `PASS | FAIL`
- Not Before: `__________________`
- Not After: `__________________`
- Chain validation result: `PASS | FAIL`
- TLS handshake warnings: `NONE | DETAILS`
- HTTP -> HTTPS redirect on app endpoint: `PASS | FAIL`

Captured output snippet:

```text
subject=((('commonName', '*.vercel.app'),),)
issuer=((('countryName', 'US'),), (('organizationName', 'Google Trust Services'),), (('commonName', 'WR1'),))
not_before=Apr 28 02:04:43 2026 GMT
not_after=Jul 27 02:04:42 2026 GMT
```

HTTP redirect verification snippet:

```text
http://optimo-virtual-try-on-rose.vercel.app  ->  connection refused (port 80 closed)
tls_connect=ok on 443
```

## 5) Automated Guardrails

- Frontend compliance guard:
  - `npm run compliance:guard`
  - Expected: `Compliance guard passed.`
- Backend targeted tests:
  - `pytest tests/test_shopify_orders_graphql.py tests/test_billing_activate_guardrails.py tests/test_widget_cart_payload_guard.py`

# Backend TLS Verification Checklist

Use this before Shopify App Store submission.

## Endpoint

- Backend base URL (production):
- Date/time verified:

## Certificate checks

- [ ] Endpoint responds over `https://`.
- [ ] Certificate is valid (not expired).
- [ ] Hostname/SAN matches backend domain.
- [ ] Full chain validates to trusted root.
- [ ] TLS handshake succeeds without browser warnings.

## Suggested command evidence

```bash
openssl s_client -connect <backend-domain>:443 -servername <backend-domain> -showcerts
```

- [ ] Save command output in submission evidence folder.
- [ ] Record certificate `Not Before` and `Not After` dates.


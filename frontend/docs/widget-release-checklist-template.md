# Widget Release Checklist

- Release date:
- Widget version (`extensions/storefront-widget/widget-release.json`):
- Extension deploy identifier/version:
- Target shop domain:
- Target theme:
- Live product URL verified:
- `npm run widget:verify` result:
- `npm run compliance:guard` result:
- Notes / regressions:

## Compliance Assertions

- [ ] Theme app extension is the only storefront install path.
- [ ] No `write_script_tags` scope present.
- [ ] Widget cart payload includes only `id` and `quantity` (no hidden fees/properties).
- [ ] No App Bridge max/fullscreen modal auto-launch behavior introduced.

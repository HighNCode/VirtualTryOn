# Script Tag Deprecation Migration Note

## Effective Date

- May 26, 2026

## Change

- Legacy ScriptTag storefront injection is deprecated.
- Theme App Extension is now the only supported storefront integration path.

## What changed technically

- `write_script_tags` removed from app scopes.
- OAuth install flow no longer installs ScriptTags.
- Uninstall flow no longer depends on ScriptTag cleanup.

## Merchant impact

- Existing merchants should add the Optimo VTS widget block via Shopify Theme Editor.
- If widget is not visible after update, merchants must complete Theme Setup and click `Check again`.

## Support guidance

- Route storefront activation issues to Theme Setup screen.
- Do not troubleshoot ScriptTag installation for new releases.


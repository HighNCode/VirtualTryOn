# Max Modal Compliance Note (Requirement 2.2.7)

## Finding

- No Shopify App Bridge `ResourcePicker` auto-launch flow is present in current app code paths.
- No fullscreen/max modal is triggered on page load.

## Current behavior

- UI interactions that navigate or open billing are user initiated (button click actions).
- Storefront widget overlay is customer-triggered via explicit button interaction.

## Regression guard

- Add this check to release review: reject any change that opens App Bridge ResourcePicker/max modal without direct merchant action.


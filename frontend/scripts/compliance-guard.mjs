#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

function read(relPath) {
  return fs.readFileSync(path.join(root, relPath), "utf8");
}

const shopifyAppToml = read("shopify.app.toml");
if (/write_script_tags/.test(shopifyAppToml)) {
  fail("write_script_tags scope detected in shopify.app.toml");
}

const widgetJs = read("extensions/storefront-widget/assets/optimo-vts-widget.js");
if (!/body:\s*JSON\.stringify\(\{\s*[\s\S]*id:\s*variant\.id[\s\S]*quantity:\s*1[\s\S]*\}\)/m.test(widgetJs)) {
  fail("Widget add-to-cart payload no longer matches expected minimal shape.");
}
if (/selling_plan\s*:/.test(widgetJs) || /properties\s*:/.test(widgetJs)) {
  fail("Widget add-to-cart payload includes selling_plan/properties fields.");
}

const appCode = read("web/app/settings/billing/page.tsx") + "\n" + read("web/app/step-6/page.tsx");
if (!/billing_status/.test(appCode)) {
  fail("Billing return status handling marker not found.");
}

const backendAuth = read("../backend/app/api/v1/auth.py");
const backendWebhooks = read("../backend/app/api/v1/webhooks.py");
const backendShopifyService = read("../backend/app/services/shopify_service.py");
if (
  /install_script_tag\(/.test(backendAuth) ||
  /delete_script_tag\(/.test(backendWebhooks) ||
  /def\s+install_script_tag\(/.test(backendShopifyService) ||
  /def\s+delete_script_tag\(/.test(backendShopifyService)
) {
  fail("Legacy script-tag runtime calls detected in backend auth/webhook flows.");
}

const storefrontWidget = read("extensions/storefront-widget/assets/optimo-vts-widget.js");
const billingPage = read("web/app/settings/billing/page.tsx");
const onboardingBillingPage = read("web/app/step-6/page.tsx");
const checkoutSurface = `${storefrontWidget}\n${billingPage}\n${onboardingBillingPage}`;
if (/https?:\/\/[^"'\s]+\/(?:checkout|payments?)/i.test(checkoutSurface)) {
  fail("Potential offsite checkout/payment URL pattern detected in storefront/billing surfaces.");
}

console.log("Compliance guard passed.");

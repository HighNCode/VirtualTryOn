import { readWidgetReleaseManifest } from "./widget-version-lib.mjs";

function readArgValue(flagName) {
  const index = process.argv.indexOf(flagName);
  if (index === -1) return "";
  return process.argv[index + 1] || "";
}

function fail(message) {
  console.error(`Widget verification failed: ${message}`);
  process.exit(1);
}

const pageUrl = readArgValue("--url").trim();
const explicitVersion = readArgValue("--version").trim();

if (!pageUrl) {
  fail("Missing --url. Example: npm run widget:verify -- --url \"https://shop.com/products/item\"");
}

const expectedVersion = explicitVersion || readWidgetReleaseManifest().version;

if (typeof fetch !== "function") {
  fail("Global fetch is unavailable in this Node runtime.");
}

const pageResponse = await fetch(pageUrl, { method: "GET" });
if (!pageResponse.ok) {
  fail(`Could not fetch storefront page (${pageResponse.status}).`);
}

const html = await pageResponse.text();
const markerMatch = html.match(/data-optimo-vts-widget-version="([^"]+)"/i);
if (!markerMatch) {
  fail("Could not find data-optimo-vts-widget-version marker in storefront HTML.");
}

const pageVersion = markerMatch[1];
if (pageVersion !== expectedVersion) {
  fail(`Storefront marker version mismatch. Expected ${expectedVersion}, got ${pageVersion}.`);
}

const scriptMatch = html.match(/<script[^>]+src="([^"]*optimo-vts-widget\.js[^"]*)"[^>]*><\/script>/i);
if (!scriptMatch) {
  fail("Could not find optimo-vts-widget.js script tag in storefront HTML.");
}

const scriptUrl = new URL(scriptMatch[1], pageUrl);
const cacheToken = scriptUrl.searchParams.get("v") || "";
if (cacheToken !== expectedVersion) {
  fail(`Widget asset cache token mismatch. Expected ${expectedVersion}, got ${cacheToken || "(missing)"}.`);
}

const scriptResponse = await fetch(scriptUrl, { method: "GET" });
if (!scriptResponse.ok) {
  fail(`Could not fetch widget JS asset (${scriptResponse.status}).`);
}

const scriptSource = await scriptResponse.text();
const buildLine = `const OVTS_WIDGET_BUILD = "${expectedVersion}";`;
if (!scriptSource.includes(buildLine)) {
  fail(`Widget runtime build marker is missing expected version ${expectedVersion}.`);
}

console.log("Widget storefront verification passed.");
console.log(`- URL: ${pageUrl}`);
console.log(`- version marker: ${pageVersion}`);
console.log(`- asset URL: ${scriptUrl.toString()}`);


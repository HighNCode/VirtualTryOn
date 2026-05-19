import { readWidgetReleaseManifest } from "./widget-version-lib.mjs";

const { version } = readWidgetReleaseManifest();

console.log("");
console.log("Widget release completed.");
console.log(`Widget version: ${version}`);
console.log("");
console.log("Next verification steps:");
console.log("1. In Shopify Admin, ensure the latest app extension version is active on the target live theme.");
console.log("2. Run storefront verification:");
console.log(`   npm run widget:verify -- --url \"https://<shop-domain>/products/<handle>\" --version \"${version}\"`);
console.log("3. Record release notes with:");
console.log("   - widget version");
console.log("   - extension deploy identifier/version");
console.log("   - target theme");
console.log("   - live URL verification result");


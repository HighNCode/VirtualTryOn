import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

function readClientIdFromShopifyConfig() {
  try {
    const configPath = path.resolve(currentDir, "..", "shopify.app.toml");
    const content = fs.readFileSync(configPath, "utf8");
    const match = content.match(/^\s*client_id\s*=\s*"([^"]+)"/m);
    return match?.[1] ?? "";
  } catch {
    return "";
  }
}

const shopifyApiKey =
  process.env.SHOPIFY_API_KEY?.trim() ||
  readClientIdFromShopifyConfig() ||
  process.env.NEXT_PUBLIC_SHOPIFY_API_KEY?.trim() ||
  "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_SHOPIFY_API_KEY: shopifyApiKey
  }
};

export default nextConfig;

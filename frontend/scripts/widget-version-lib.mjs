import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));

export const frontendRoot = path.resolve(scriptDir, "..");
export const widgetReleaseManifestPath = path.join(
  frontendRoot,
  "extensions",
  "storefront-widget",
  "widget-release.json"
);
export const widgetJsPath = path.join(
  frontendRoot,
  "extensions",
  "storefront-widget",
  "assets",
  "optimo-vts-widget.js"
);
export const widgetLiquidPath = path.join(
  frontendRoot,
  "extensions",
  "storefront-widget",
  "blocks",
  "optimo_vts_widget.liquid"
);

const SEMVER_PATTERN = /^\d+\.\d+\.\d+$/;

export function assertSemver(version) {
  if (!SEMVER_PATTERN.test(String(version || ""))) {
    throw new Error(`Invalid widget version "${version}". Use semver format like 1.0.0.`);
  }
}

export function readWidgetReleaseManifest() {
  const raw = fs.readFileSync(widgetReleaseManifestPath, "utf8");
  const parsed = JSON.parse(raw);
  const version = String(parsed.version || "").trim();
  assertSemver(version);
  return { version };
}

export function writeWidgetReleaseManifest(version) {
  assertSemver(version);
  const content = `${JSON.stringify({ version }, null, 2)}\n`;
  fs.writeFileSync(widgetReleaseManifestPath, content, "utf8");
}

export function bumpPatchVersion(version) {
  assertSemver(version);
  const [major, minor, patch] = version.split(".").map((value) => Number.parseInt(value, 10));
  return `${major}.${minor}.${patch + 1}`;
}

function replaceOrThrow(content, pattern, replacement, label) {
  if (!pattern.test(content)) {
    throw new Error(`Could not find version marker in ${label}.`);
  }
  return content.replace(pattern, replacement);
}

export function syncWidgetVersionFiles(version, options = {}) {
  assertSemver(version);
  const shouldWrite = options.write !== false;
  const changedFiles = [];

  const jsSource = fs.readFileSync(widgetJsPath, "utf8");
  const nextJsSource = replaceOrThrow(
    jsSource,
    /const OVTS_WIDGET_BUILD = "[^"]+";/,
    `const OVTS_WIDGET_BUILD = "${version}";`,
    widgetJsPath
  );
  if (nextJsSource !== jsSource) {
    changedFiles.push(widgetJsPath);
    if (shouldWrite) {
      fs.writeFileSync(widgetJsPath, nextJsSource, "utf8");
    }
  }

  const liquidSource = fs.readFileSync(widgetLiquidPath, "utf8");
  const nextLiquidSource = replaceOrThrow(
    liquidSource,
    /assign widget_version = '[^']+'/,
    `assign widget_version = '${version}'`,
    widgetLiquidPath
  );
  if (nextLiquidSource !== liquidSource) {
    changedFiles.push(widgetLiquidPath);
    if (shouldWrite) {
      fs.writeFileSync(widgetLiquidPath, nextLiquidSource, "utf8");
    }
  }

  return changedFiles;
}


import path from "node:path";
import {
  frontendRoot,
  readWidgetReleaseManifest,
  syncWidgetVersionFiles,
  widgetReleaseManifestPath,
} from "./widget-version-lib.mjs";

function readArgValue(flagName) {
  const index = process.argv.indexOf(flagName);
  if (index === -1) return "";
  return process.argv[index + 1] || "";
}

function fail(message) {
  console.error(`Widget guard failed: ${message}`);
  process.exit(1);
}

const baseRef = readArgValue("--base") || process.env.BASE_SHA || "HEAD~1";
const changedFilesRaw =
  readArgValue("--changed-files") ||
  process.env.WIDGET_CHANGED_FILES ||
  "";

if (!changedFilesRaw.trim()) {
  fail(
    "No changed files were provided. Pass --changed-files or set WIDGET_CHANGED_FILES."
  );
}

const changedFiles = changedFilesRaw
  .split(/[,\n;\r]+/)
  .map((value) => value.trim())
  .filter(Boolean)
  .map((value) => value.replace(/\\/g, "/"));

if (!changedFiles.length) {
  console.log("Widget guard: no changed files.");
  process.exit(0);
}

const watchedPrefixes = [
  "frontend/extensions/storefront-widget/assets/",
  "frontend/extensions/storefront-widget/blocks/",
];
const normalizedManifestPath = path
  .relative(path.resolve(frontendRoot, ".."), widgetReleaseManifestPath)
  .replace(/\\/g, "/");

const widgetSourceChanged = changedFiles.some((filePath) =>
  watchedPrefixes.some((prefix) => filePath.startsWith(prefix))
);
const manifestChanged = changedFiles.includes(normalizedManifestPath);

if (widgetSourceChanged && !manifestChanged) {
  fail(`Widget source changed without version bump in ${normalizedManifestPath}.`);
}

const { version } = readWidgetReleaseManifest();
const unsyncedFiles = syncWidgetVersionFiles(version, { write: false });
if (unsyncedFiles.length) {
  fail(`Widget files are not synced to version ${version}. Run: npm run widget:version:sync`);
}

console.log("Widget guard passed.");
console.log(`- base ref: ${baseRef}`);
console.log(`- changed files: ${changedFiles.length}`);
console.log(`- widget source changed: ${widgetSourceChanged}`);
console.log(`- version manifest changed: ${manifestChanged}`);

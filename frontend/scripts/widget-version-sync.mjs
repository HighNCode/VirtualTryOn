import { readWidgetReleaseManifest, syncWidgetVersionFiles } from "./widget-version-lib.mjs";

const { version } = readWidgetReleaseManifest();
const changedFiles = syncWidgetVersionFiles(version, { write: true });

if (changedFiles.length) {
  console.log(`Synced widget version ${version} to:`);
  changedFiles.forEach((filePath) => console.log(`- ${filePath}`));
} else {
  console.log(`Widget files already match version ${version}.`);
}


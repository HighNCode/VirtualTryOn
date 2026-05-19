import {
  bumpPatchVersion,
  readWidgetReleaseManifest,
  syncWidgetVersionFiles,
  writeWidgetReleaseManifest,
} from "./widget-version-lib.mjs";

const current = readWidgetReleaseManifest();
const nextVersion = bumpPatchVersion(current.version);

writeWidgetReleaseManifest(nextVersion);
const changedFiles = syncWidgetVersionFiles(nextVersion, { write: true });

console.log(`Widget version bumped: ${current.version} -> ${nextVersion}`);
if (changedFiles.length) {
  console.log("Updated widget sources:");
  changedFiles.forEach((filePath) => console.log(`- ${filePath}`));
}


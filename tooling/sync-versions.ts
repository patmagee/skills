import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { repoPaths } from "./paths.js";

function readVersion(path: string, extract: (json: any) => string | undefined): string {
  const version = extract(JSON.parse(readFileSync(path, "utf8")));
  if (!version) throw new Error(`No version found in ${path}`);
  return version;
}

function replaceVersion(path: string, from: string, to: string): void {
  const text = readFileSync(path, "utf8");
  const needle = `"version": "${from}"`;
  if (!text.includes(needle)) {
    throw new Error(`Expected ${needle} in ${path}`);
  }
  writeFileSync(path, text.replaceAll(needle, `"version": "${to}"`));
}

/**
 * Copies package.json's version into plugin.json and marketplace.json.
 * package.json is the source of truth: bump it first (e.g. `npm version
 * minor --no-git-tag-version`), then run this to bring the plugin
 * manifests back in sync. Returns the propagated version.
 */
export function syncManifestVersions(root: string): string {
  const paths = repoPaths(root);
  const target = readVersion(paths.packageJson, (j) => j.version);
  for (const [path, extract] of [
    [paths.pluginJson, (j: any) => j.version],
    [paths.marketplaceJson, (j: any) => j.plugins?.[0]?.version],
  ] as const) {
    const current = readVersion(path, extract);
    if (current !== target) replaceVersion(path, current, target);
  }
  return target;
}

const invokedDirectly =
  process.argv[1] && process.argv[1] === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  try {
    console.log(syncManifestVersions(process.cwd()));
  } catch (err) {
    console.error((err as Error).message);
    process.exit(1);
  }
}

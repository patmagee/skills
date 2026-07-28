import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtempSync, mkdirSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { syncManifestVersions } from "./sync-versions.js";

let root: string;

function write(rel: string, content: string): void {
  writeFileSync(join(root, rel), content);
}

function read(rel: string): string {
  return readFileSync(join(root, rel), "utf8");
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "sync-versions-"));
  mkdirSync(join(root, ".claude-plugin"));
  write("package.json", `{\n  "name": "x",\n  "version": "1.3.0"\n}\n`);
  write(
    ".claude-plugin/plugin.json",
    `{\n  "name": "x",\n  "version": "1.2.1",\n  "skills": []\n}\n`,
  );
  write(
    ".claude-plugin/marketplace.json",
    `{\n  "name": "m",\n  "plugins": [\n    {\n      "name": "x",\n      "version": "1.2.1",\n      "source": "./"\n    }\n  ]\n}\n`,
  );
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true });
});

describe("syncManifestVersions", () => {
  it("propagates package.json's version into both plugin manifests", () => {
    expect(syncManifestVersions(root)).toBe("1.3.0");
    expect(JSON.parse(read(".claude-plugin/plugin.json")).version).toBe("1.3.0");
    expect(JSON.parse(read(".claude-plugin/marketplace.json")).plugins[0].version).toBe("1.3.0");
  });

  it("only touches the version field, preserving formatting", () => {
    const before = read(".claude-plugin/plugin.json");
    syncManifestVersions(root);
    expect(read(".claude-plugin/plugin.json")).toBe(before.replace("1.2.1", "1.3.0"));
  });

  it("is a no-op when versions already match", () => {
    write(".claude-plugin/plugin.json", `{\n  "version": "1.3.0"\n}\n`);
    write(
      ".claude-plugin/marketplace.json",
      `{\n  "plugins": [{ "name": "x", "version": "1.3.0" }]\n}\n`,
    );
    expect(syncManifestVersions(root)).toBe("1.3.0");
  });

  it("throws when a manifest has no version", () => {
    write(".claude-plugin/marketplace.json", `{\n  "plugins": []\n}\n`);
    expect(() => syncManifestVersions(root)).toThrow(/marketplace\.json/);
  });
});

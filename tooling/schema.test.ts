import { describe, it, expect } from "vitest";
import { normalizeFrontmatter, titleCase, firstSentence } from "./schema.js";

describe("titleCase", () => {
  it("converts a hyphenated slug to title case", () => {
    expect(titleCase("consensus-planning")).toBe("Consensus Planning");
  });
});

describe("firstSentence", () => {
  it("returns text up to the first period", () => {
    expect(firstSentence("Does a thing. And more.")).toBe("Does a thing.");
  });
  it("returns the whole string when there is no period", () => {
    expect(firstSentence("No period here")).toBe("No period here");
  });
});

describe("normalizeFrontmatter", () => {
  it("applies defaults for optional fields", () => {
    const fm = normalizeFrontmatter(
      { name: "consensus-planning", description: "Plans things. In rounds." },
      "consensus-planning",
    );
    expect(fm.invocation).toBe("model");
    expect(fm.harnesses).toEqual(["claude", "codex", "cursor"]);
    expect(fm.displayName).toBe("Consensus Planning");
    expect(fm.shortDescription).toBe("Plans things.");
    expect(fm.disableModelInvocation).toBe(false);
  });

  it("derives disableModelInvocation from invocation: user", () => {
    const fm = normalizeFrontmatter(
      { name: "brag-doc", description: "User run.", invocation: "user" },
      "brag-doc",
    );
    expect(fm.disableModelInvocation).toBe(true);
  });

  it("honors explicit optional fields", () => {
    const fm = normalizeFrontmatter(
      {
        name: "x",
        description: "d.",
        harnesses: ["claude"],
        display_name: "Custom Name",
        short_description: "Custom short",
      },
      "x",
    );
    expect(fm.harnesses).toEqual(["claude"]);
    expect(fm.displayName).toBe("Custom Name");
    expect(fm.shortDescription).toBe("Custom short");
  });

  it("trims short_description so YAML block scalars cannot break table rows", () => {
    const fm = normalizeFrontmatter(
      {
        name: "x",
        description: "Long description. Detail.",
        short_description: "Folded scalar value\n",
      },
      "x",
    );
    expect(fm.shortDescription).toBe("Folded scalar value");
  });

  it("throws when name is missing", () => {
    expect(() => normalizeFrontmatter({ description: "d." }, "x")).toThrow(/name/);
  });

  it("throws on an unknown harness", () => {
    expect(() =>
      normalizeFrontmatter(
        { name: "x", description: "d.", harnesses: ["vim"] },
        "x",
      ),
    ).toThrow(/harness/i);
  });
});

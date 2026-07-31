import { z } from "zod";

export type Harness = "claude" | "codex" | "cursor";
export const ALL_HARNESSES: Harness[] = ["claude", "codex", "cursor"];

export interface NormalizedFrontmatter {
  name: string;
  description: string;
  invocation: "model" | "user";
  harnesses: Harness[];
  displayName: string;
  shortDescription: string;
  disableModelInvocation: boolean;
}

export interface Skill {
  slug: string;
  dir: string;
  body: string;
  frontmatter: NormalizedFrontmatter;
}

const harnessSchema = z.enum(["claude", "codex", "cursor"]);

const rawSchema = z.object({
  name: z.string().min(1),
  description: z.string().min(1),
  invocation: z.enum(["model", "user"]).default("model"),
  harnesses: z.array(harnessSchema).nonempty().default(() => [...ALL_HARNESSES]),
  display_name: z.string().min(1).optional(),
  short_description: z.string().min(1).optional(),
});

export function titleCase(slug: string): string {
  return slug
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function firstSentence(text: string): string {
  const idx = text.indexOf(".");
  return idx === -1 ? text.trim() : text.slice(0, idx + 1).trim();
}

export function normalizeFrontmatter(
  raw: unknown,
  slug: string,
): NormalizedFrontmatter {
  const parsed = rawSchema.safeParse(raw);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
      .join("; ");
    throw new Error(`Invalid frontmatter in "${slug}": ${issues}`);
  }
  const fm = parsed.data;
  return {
    name: fm.name,
    description: fm.description,
    invocation: fm.invocation,
    harnesses: fm.harnesses,
    displayName: fm.display_name ?? titleCase(fm.name),
    shortDescription:
      fm.short_description?.trim() ?? firstSentence(fm.description),
    disableModelInvocation: fm.invocation === "user",
  };
}

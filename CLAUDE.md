# CLAUDE.md — Skills Repository

## What This Is

A personal collection of Claude skills. Each skill is a self-contained prompt package that gives Claude specialized capabilities for complex tasks. Skills are organized one-per-directory at the repo root.

## Repo Layout

```
skills/                             # The repo
├── README.md                       # Repo overview and skill index
├── CLAUDE.md                       # This file
├── .gitignore
└── skills/                         # All skills live here
    └── consensus-planning/         # One directory per skill
        ├── SKILL.md                # Entry point (required)
        ├── agents/                 # Agent prompts
        ├── references/             # Schemas, templates, guides
        ├── scripts/                # Helper scripts
        ├── README.md               # Skill-specific human docs
        └── CLAUDE.md               # Skill-specific dev/AI docs
```

## Conventions

Each skill lives under `skills/<name>/` with `SKILL.md` at the top level of that directory. This flat structure is required for the plugin system to auto-discover skills.

SKILL.md is always the entry point. It contains the orchestration instructions that Claude follows when the skill is triggered. Frontmatter at the top of SKILL.md declares the skill's name, description, and trigger phrases.

## Adding a Skill

1. Create `skills/<skill-name>/` under the skills directory
2. Create `skills/<skill-name>/SKILL.md` with frontmatter and instructions
3. Add supporting files (agents/, references/, scripts/) in the same directory
4. Add `skills/<skill-name>/README.md` for human documentation
5. Add `skills/<skill-name>/CLAUDE.md` for architecture and modification notes
6. Update the root README.md skills table

## Current Skills

- **consensus-planning** — Multi-agent consensus planning. Spawns analyst agents with perspective-based analytical styles to solve problems through structured rounds of critique, revision, and review. See `skills/consensus-planning/CLAUDE.md` for architecture details.
- **design-memory** — Cross-repo vector store for design docs and decision records. Indexes specs with YAML frontmatter and decision confidence tiers, then surfaces prior decisions during brainstorm sessions. Requires ChromaDB and Gemini embeddings. See `skills/design-memory/SKILL.md` for commands.
- **dual-adversarial-review** — Runs two adversarial reviewers in parallel (Claude Opus plus Codex) against a spec, plan, or diff, then synthesizes an accept/reject table. Needs the Codex CLI plugin for the second reviewer; degrades to Claude-only. See `skills/dual-adversarial-review/README.md`.
- **ms-frizzle** — Directed experimentation for learning through hands-on probes when there is no spec yet. Structures a session as a field trip: one driving question, one falsifiable experiment per leg, a findings ledger, and a forced synthesis at the end. See `skills/ms-frizzle/README.md`.
- **two-pass-review** — Pre-merge review in two passes with opposite framings: a deep semantic reviewer and an exhaustive mechanical checklist, merged into one verified findings list. `--mode dual` upgrades the semantic pass to the dual-adversarial-review panel. See `skills/two-pass-review/README.md`.

## Runtime Artifacts

Skills may generate runtime files (JSON session state, log files, output documents) during execution. These are created in a `planning/` or similar working directory at runtime — not checked into the repo. The `.gitignore` excludes common patterns.

## Releases

Versions are bumped automatically. On every merge to `main`, the release workflow (`.github/workflows/release.yml`) bumps the minor version in `package.json`, `plugin.json`, and `marketplace.json`, tags the commit, and publishes a GitHub release. Never bump these versions by hand in a PR; the validate CI job checks that all three stay in sync. Add `[skip release]` to a merge commit message to skip the release.

## Dependencies

Most skills use Python 3 standard library only. Exceptions:

- **design-memory** — Requires `chromadb`, `google-genai`, `pyyaml` installed in its own venv. See `skills/design-memory/SKILL.md` for setup.

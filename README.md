# Skills

A personal collection of Claude skills — structured prompt packages that give Claude specialized capabilities for complex, multi-step tasks.

Each skill lives in its own directory and follows the Claude skill format: a `SKILL.md` entry point, optional agent prompts, reference documents, and helper scripts.

## Available Skills

<!-- SKILLS:START -->
| Skill | Description | Invocation |
| --- | --- | --- |
| [consensus-planning](skills/consensus-planning/SKILL.md) | Multi-agent consensus planning system. | model |
| [design-memory](skills/design-memory/SKILL.md) | Manage a local vector store of design docs and decision records across all repos. | model |
| [dual-adversarial-review](skills/dual-adversarial-review/SKILL.md) | Run two adversarial reviewers (Claude Opus + Codex) in parallel against a spec, plan, or diff, then synthesize an accept/reject table. | model |
| [ms-frizzle](skills/ms-frizzle/SKILL.md) | Use when the user wants to learn or understand something through hands-on experimentation and doesn't yet know what the spec or deliverable should look like — "let's poke at X", "I want to understand how Y actually works", "what would happen if", "field trip", or an explicit /ms-frizzle. | model |
| [two-pass-review](skills/two-pass-review/SKILL.md) | Use before requesting human review or merging, when one review pass keeps missing a whole class of defect — deep semantic/contract bugs on one side, mechanical/local nits (null-safety, unsafe casts, unused deps, doc-vs-code drift, dead annotations, invalid generated specs) on the other. | model |
<!-- SKILLS:END -->

## Skill Structure

All skills live under the `skills/` directory. Each skill follows this convention:

```
skills/
└── <skill-name>/
    ├── <skill-name>/
    │   ├── SKILL.md              # Entry point — orchestration instructions
    │   ├── agents/               # Agent prompt templates (if multi-agent)
    │   ├── references/           # Schemas, guides, templates
    │   └── scripts/              # Helper scripts
    ├── README.md                 # Human-readable documentation
    └── CLAUDE.md                 # Developer/AI-facing reference
```

The inner `<skill-name>/` directory is what gets loaded as the skill. The outer directory holds documentation and any supporting files.

## Adding a New Skill

1. Create a directory under `skills/` named after the skill
2. Inside it, create another directory with the same name containing `SKILL.md`
3. Add agent prompts, references, and scripts as needed
4. Add a `README.md` alongside the inner directory documenting the skill for humans
5. Add a `CLAUDE.md` with architecture notes, modification guides, and testing instructions
6. Update this table with the new skill

## Usage

These skills can be installed into Claude by pointing it at the skill directory. Trigger phrases and activation instructions are documented in each skill's `SKILL.md` frontmatter.

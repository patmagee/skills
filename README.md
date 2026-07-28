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

## Installing as a Plugin

This repository is a Claude Code plugin marketplace. The marketplace manifest lives at `.claude-plugin/marketplace.json` and exposes one plugin, `patmagee-skills`, which bundles every skill in the table above.

### Add the marketplace and install

Run these commands inside Claude Code:

```
/plugin marketplace add patmagee/skills
/plugin install patmagee-skills@patmagee-marketplace
```

The first command registers this GitHub repository as a marketplace named `patmagee-marketplace` (the name comes from `marketplace.json`, not the repository URL). The second command installs the plugin from it. After installation, every skill is available by its name, for example `/ms-frizzle` or `/two-pass-review`.

### Update

To pull the latest version of the plugin after new skills land:

```
/plugin marketplace update patmagee-marketplace
```

### Disable or remove

```
/plugin disable patmagee-skills@patmagee-marketplace
/plugin uninstall patmagee-skills@patmagee-marketplace
/plugin marketplace remove patmagee-marketplace
```

`disable` keeps the plugin installed but inactive. `uninstall` removes it. Removing the marketplace also removes its plugins.

### Preconfigure for a team or project

To make the marketplace and plugin available automatically for everyone working in a repository, add both keys to that repository's `.claude/settings.json` (or to `~/.claude/settings.json` for a single user):

```json
{
  "extraKnownMarketplaces": {
    "patmagee-marketplace": {
      "source": {
        "source": "github",
        "repo": "patmagee/skills"
      }
    }
  },
  "enabledPlugins": {
    "patmagee-skills@patmagee-marketplace": true
  }
}
```

Claude Code will prompt each person to trust the marketplace the first time they open the project.

### Local development install

To test changes to a skill before pushing, add your local checkout as a marketplace and install from it:

```
/plugin marketplace add /path/to/your/checkout
/plugin install patmagee-skills@patmagee-marketplace
```

A local marketplace reads the working tree, so edits to a `SKILL.md` are picked up without a push. Remove it with `/plugin marketplace remove patmagee-marketplace` when you switch back to the GitHub source.

## Releases

Every merge to `main` automatically bumps the minor version, tags the commit, and publishes a GitHub release. The bumped version is written to `package.json`, `.claude-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, which is what lets `/plugin marketplace update` detect that a new plugin version is available. Do not bump versions by hand. To land a change without cutting a release, include `[skip release]` in the merge commit message.

## Usage

Once installed, skills trigger in two ways: Claude invokes them automatically when a task matches the skill's description, or you invoke one explicitly by typing `/<skill-name>`. Trigger phrases and activation conditions are documented in each skill's `SKILL.md` frontmatter.

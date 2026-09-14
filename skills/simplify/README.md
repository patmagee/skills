# Simplify

Apply focused cleanup to changed code while preserving behavior and following the repository's rules. This is an explicitly invoked skill, not a bug-finding review.

## Usage

```text
/simplify
/simplify src/api/
/simplify https://github.com/owner/repo/pull/123
```

Without a target, the skill reviews uncommitted changes, including relevant untracked source files. A path narrows that scope. A PR reference selects the PR diff; applying fixes requires a matching local checkout without overlapping edits.

Four read-only reviewers examine reuse, simplification, efficiency, and abstraction. They run in parallel when the host permits it. If the host requires permission, the skill asks. If parallel execution is unavailable, the reviews run sequentially. The main agent verifies findings, applies local fixes, and runs relevant checks.

The skill avoids architectural rewrites, new dependencies, speculative optimization, and unrelated formatting. It can finish without changing anything. Possible bugs are reported separately for a dedicated correctness review.

## Installation

In Claude Code, plugin installation may expose the namespaced command `/patmagee-skills:simplify`. Codex uses the generated invocation metadata. Cursor generation is excluded because repository tooling cannot enforce user-only invocation there.

The instructions use host-neutral delegation and include a sequential fallback. No helper scripts or service credentials are required, except access to GitHub when targeting a PR.

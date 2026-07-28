# Two-Pass Review

A pre-merge review skill that runs two reviewers with opposite instructions and
synthesizes their findings. One pass is deep and low-noise (semantic: correctness,
contracts, atomicity, concurrency, test quality). The other is exhaustive and
noise-tolerant (mechanical: null-safety, unsafe casts, unused dependencies,
doc-vs-code drift, dead code, invalid generated specs).

The core idea: a single reviewer asked to be both sharp and exhaustive silently
drops the mechanical class of defects. Separating the framings closes that gap.

## When to use it

Before requesting human review or merging a diff, or after writing a plan or spec.
Trigger phrases: "two-pass review", "layered review", "catch what my review misses".
Skip it for trivial diffs; a single read is enough there.

## Modes

- `--mode single` (default): one semantic reviewer plus the mechanical pass.
- `--mode dual`: the semantic pass becomes the two-reviewer panel from the
  [dual-adversarial-review](../dual-adversarial-review/README.md) skill (Claude plus
  Codex). Reserve this for high-risk changes: auth, permissions, migrations,
  concurrency, public APIs, data-loss risk.

## Dependencies

- Dual mode needs the Codex CLI plugin (`codex:codex-rescue`); without it the skill
  falls back to the Claude reviewer only.
- Synthesis references the `superpowers:receiving-code-review` skill for verifying
  findings before accepting them. The workflow still works without it; findings are
  verified against the code manually.

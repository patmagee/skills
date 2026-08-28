# Two-Pass Review

A pre-merge review skill that runs two reviewers with opposite instructions and
synthesizes their findings. One pass is deep and low-noise (semantic: correctness,
contracts, atomicity, concurrency, test quality). The other is exhaustive and
noise-tolerant (mechanical: null-safety, unsafe casts, unused dependencies,
doc-vs-code drift, dead code, invalid generated specs, and unproven quantified
claims in comments).

The core idea: a single reviewer asked to be both sharp and exhaustive silently
drops the mechanical class of defects. Separating the framings closes that gap.

## Explicit-only

Invoke this skill by name (`/two-pass-review`). It does not trigger from a generic
"review this" request. When Pi Flow is active, `reviewing-change-sets` is the review
orchestrator; run `reviewing-change-sets layered` or `reviewing-change-sets stacked`
instead, and do not run both orchestrators at the same checkpoint.

## When to use it

Before requesting human review or merging a diff, or after writing a plan or spec,
when you have explicitly chosen a two-pass review. Skip it for trivial diffs; a single
read is enough there.

## Modes

- `--mode layered` (default): one semantic reviewer plus the mechanical pass. Two seats.
- `--mode stacked` (explicit only): the semantic pass becomes the two-reviewer panel
  from the [dual-adversarial-review](../dual-adversarial-review/README.md) skill (Claude
  plus Codex, different model families), plus the mechanical pass. Three seats. Reserve
  it for high-risk changes: auth, permissions, migrations, concurrency, public APIs,
  data-loss risk, and only when the caller accepts the added cost.

### Compatibility aliases

- `--mode single` maps to `layered`.
- `--mode dual` no longer runs. The old `dual` silently added a third seat. Select
  `stacked` explicitly for two semantic reviewers plus the mechanical reviewer, or use
  `layered` otherwise.

The `layered` and `stacked` mode names match Pi Flow `reviewing-change-sets`: `layered` is one
semantic plus one mechanical reviewer, and `stacked` is two semantic reviewers plus one mechanical
reviewer. The `single` and `dual` names are two-pass compatibility aliases only; they do not map to
Pi Flow's `single` and `dual` modes, which carry no mechanical seat.

## Independent oracle

Give each semantic reviewer the approved contract and the raw evidence, not the prior
reviewer's verdict, and do not describe the current detector or fix as correct. For a
parser, rewriter, or validator, require the reviewer to derive an attack matrix from the
contract before judging the implementation. More seats over the same oracle repeat one
blind spot.

## Dependencies

- Stacked mode needs the Codex CLI plugin (`codex:codex-rescue`); without it the skill
  falls back to the Claude reviewer only.
- Synthesis references the `superpowers:receiving-code-review` skill for verifying
  findings before accepting them. The workflow still works without it; findings are
  verified against the code manually.

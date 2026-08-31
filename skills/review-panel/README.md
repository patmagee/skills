# Review Panel

Review Panel is an explicit pre-merge review skill. Its correctness core uses reviewers with
opposite instructions. One semantic reviewer checks behavior, contracts, concurrency, and test
quality. One mechanical reviewer checks every changed hunk for local defects.

Two optional seats answer different questions. The design seat asks whether the change has the right
shape. The security seat checks the trust model.

## Explicit-only

Invoke this skill by name with `/review-panel`. A generic review request does not trigger it. The
deprecated `/two-pass-review` command loads the same workflow. When Pi Flow is active, use its
`reviewing-change-sets` flow instead. Do not run both review orchestrators at the same checkpoint.

## Correctness modes

- `--mode layered` is the default. It runs one semantic reviewer and one mechanical reviewer.
- `--mode stacked` runs two independent semantic reviewers from different model families and one
  mechanical reviewer. It has higher cost and requires an explicit choice.

`--mode single` remains an alias for `layered`. The ambiguous old `--mode dual` no longer runs.

## Optional seats

- `--design` adds a design and architecture reviewer. Supply the change's goal or intent when one
  exists. If it does not, the reviewer uses SOLID and Don't Repeat Yourself (DRY), prefers
  composition for API objects, and accepts inheritance only for a genuine substitutable API
  relationship. The result states when it uses this fallback.
- `--security` adds a trust-model reviewer. It checks boundaries, permissions, injection, data and
  secret exposure, server-side request forgery, tenant isolation, and abuse paths. This seat is off
  by default.

The options compose with either correctness mode. For example:

```text
/review-panel --mode layered --design
/review-panel --mode stacked --security
/review-panel --mode layered --design --security
```

All selected reviewers run in one parallel batch. Each receives raw evidence and its own review
standard. No reviewer receives another reviewer's verdict.

## Results

The synthesis reports separate sections for correctness, design, and security. It does not blend
their severity systems. A final shared-seams section notes when design and correctness findings
concern the same API, boundary, layer, or contract.

## Dependencies

Stacked mode needs the Codex CLI plugin used by
[dual-adversarial-review](../dual-adversarial-review/README.md). Without it, the skill falls back to
the Claude semantic reviewer.

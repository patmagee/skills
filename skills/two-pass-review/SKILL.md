---
name: two-pass-review
description: >-
  Explicit-only layered review that runs a semantic pass and a mechanical pass
  with opposite instructions, then synthesizes. Invoke it by name only: a
  generic review request must not trigger it. Modes: layered (default, one
  semantic plus one mechanical) and stacked (explicit only, two semantic from
  different model families plus one mechanical). Pi Flow users should normally
  invoke reviewing-change-sets layered or reviewing-change-sets stacked instead.
invocation: user
disable-model-invocation: true
---

# Two-Pass Review

## Overview

A single reviewer optimizes for one thing and drops the other. A sharp *semantic* reviewer skims
boilerplate and misses null-checks, doc drift, unused deps, and invalid generated specs; a
*mechanical* linter never reaches cross-path contracts, atomicity, or tests that pass even when the
code is broken. Run **two passes with opposite instructions** — one deep and low-noise, one
exhaustive and noise-tolerant — then synthesize.

**Core principle: never ask one reviewer to be both sharp and exhaustive — the framings conflict and
the mechanical class silently gets dropped.**

## Explicit-only

Invoke this skill by name (`/two-pass-review`). It does not trigger from a generic "review this"
request. When Pi Flow is active, `reviewing-change-sets` is the review orchestrator: run
`reviewing-change-sets layered` or `reviewing-change-sets stacked` instead of this skill, and do not
run both orchestrators at the same checkpoint.

## When to use

- Before requesting human review / merge on a diff or PR, when you have explicitly chosen a
  two-pass review.
- After a plan/spec, before implementation.
- When a prior review (or Copilot/Cursor) surfaced defects your own review missed.
- Not for trivial diffs (docs-only, one-line changes) — a single read is enough.

## Modes

- `--mode layered` **(default)** — Pass 1 is one semantic reviewer (Opus). Pass 2 is the mechanical
  reviewer. Two seats.
- `--mode stacked` **(explicit only)** — Pass 1 is the two-reviewer adversarial panel from the
  `dual-adversarial-review` skill (Claude Opus + Codex, different model families). Pass 2 is the
  mechanical reviewer. Three seats. Reserve for high-risk changes: auth, permissions, migrations,
  concurrency, public APIs, data-loss — and only when the caller accepts the added cost.

Pass 2 (mechanical) runs identically in both modes.

### Compatibility aliases

- `--mode single` maps to `layered`.
- `--mode dual` is ambiguous and no longer runs: the old `dual` silently added a third seat. If you
  want two semantic reviewers plus the mechanical reviewer, select `stacked` explicitly. Otherwise
  use `layered`.

The `layered` and `stacked` mode names match Pi Flow `reviewing-change-sets`, where `layered` is one
semantic plus one mechanical reviewer and `stacked` is two semantic reviewers plus one mechanical
reviewer. The `single` and `dual` names above are two-pass compatibility aliases only; they do not
map to Pi Flow's `single` and `dual` modes. Pi Flow `single` (one semantic reviewer, no mechanical
seat) and Pi Flow `dual` (two semantic reviewers, no mechanical seat) have no two-pass equivalent,
because every two-pass mode includes the mechanical pass.

## Process

1. **Identify the artifact** — working diff, PR, commit range, or plan file — plus the repo root and
   any conventions docs the reviewers must respect (e.g. `docs/java-coding-conventions.md`,
   `docs/testing-conventions.md`).
2. **Keep the semantic oracle independent.** Give each semantic reviewer the approved requirements or
   behavior contract, the raw evidence, and the relevant paths. Do not state a prior reviewer's
   verdict and do not describe the current detector or fix as correct. For a parser, rewriter,
   validator, or other heuristic transform, require the reviewer to derive an attack matrix from the
   contract before judging the implementation. If high-risk semantic behavior has no approved
   contract, stop and establish one first.
3. **Dispatch both passes in ONE message** (they are independent — run concurrently):
   - **Pass 1 — semantic.** `layered`: `Agent`, `subagent_type: general-purpose`, `model: opus`.
     `stacked`: run the two semantic reviewers as in `dual-adversarial-review` (Claude Opus +
     Codex). Prompt = **Pass 1 prompt** below.
   - **Pass 2 — mechanical.** `Agent`, `subagent_type: general-purpose`, `model: sonnet`. Prompt =
     **Pass 2 checklist** below.
4. **Synthesize** — apply `superpowers:receiving-code-review`: merge both passes, dedupe, **verify
   each finding against the code yourself**, drop false positives, order by severity. Note
   convergence (both passes flagged it → usually real).
5. **Report** the findings high→low with what you verified and the top remaining risks. This skill
   reviews; it does not implement — hand fixes to the normal edit flow.

## Pass 1 prompt — semantic (sharp, low-noise)

> Adversarial semantic reviewer. Read `<artifact>` and **verify every claim against the real code**
> (name the key files). Find: correctness bugs; cross-path / contract inconsistencies;
> atomicity / idempotency gaps; concurrency / TOCTOU; API and HTTP-status semantics; and **test
> quality** — tests that would pass even if the code broke, missing negative / boundary cases.
> Do NOT hunt mechanical nits (a separate pass owns null-checks, casts, unused deps, doc typos, dead
> code) — high signal only. Each finding: severity [BLOCKER/MAJOR/MINOR], file:line, why it's wrong,
> concrete fix. Review only — do not implement.

## Pass 2 checklist — mechanical (exhaustive, noise OK)

> Mechanical reviewer. Walk **every changed hunk**. Report every local defect — noise is acceptable,
> exhaustiveness is the goal. **Emit a verdict for EVERY changed file, even "clean"**, so no file is
> skipped. Apply each lens:

| Lens | Ask of every changed hunk |
|---|---|
| Null-safety | New field/param/return: can it be null? Deref guarded? Maps/collections defensively copied (`Map.copyOf`) and non-null? |
| Cast / type | Narrow cast safe (e.g. `Long` vs `Number` from a driver/JSON)? Unchecked or raw generics? |
| Dependencies | New build dep actually imported/used? (grep the module.) Unused import? |
| Docs vs code | Every javadoc / comment / API description near the change is a **claim** — does it still match what the code does? |
| Quantified claims | Does a changed comment or doc say **exactly**, **every**, **any**, **only**, **always**, or **never**? Prove it against the implementation. A comment claiming a heuristic detects all unsafe cases must be verified, not trusted. |
| Generated / config | OpenAPI / JSON-schema / YAML valid for its type (no `default:""` on a number)? Regenerated and in sync with annotations? Constraints (`minItems`, required, non-empty) documented? |
| Dead code | Annotation that suppresses nothing (`@SuppressWarnings`), unreachable branch, unused field/method/param? |
| Messages | Exception / log / error text matches the actual condition that triggers it? |
| Injection into interpolated strings | Untrusted input concatenated into a string that a framework then interpolates/evaluates — Bean Validation message template (`buildConstraintViolationWithTemplate`), log format, SpEL/EL, or a query built by concatenation (SQL/Cypher/JPQL)? Must be escaped or parameterized, never raw-concatenated. |
| Conventions | Matches the named conventions docs (naming, test style, formatting idioms)? |

> Each finding: severity, file:line, one-line defect, concrete fix. Review only — do not implement.

## Model & cost

- Pass 1 layered = **Opus** (reasoning-bound). Pass 2 = **Sonnet** (pattern-matchable, cheaper).
  `stacked` adds a Codex reviewer to Pass 1.
- Subagents return summaries only — keep the orchestrator context lean; relay the synthesized table,
  not the raw reviews.

## Common mistakes

| Mistake | Fix |
|---|---|
| Merging both passes into one prompt | The mechanical class gets dropped. Two separate reviewers, opposite framing. |
| No per-file verdict in Pass 2 | Boilerplate/generated files (DTOs, `build.gradle`, `*.yaml`) hide the mechanical bugs. Force a verdict per changed file. |
| Folding in findings unverified | Reviewers — and you — are wrong sometimes. Verify against code first (`receiving-code-review`). |
| Treating `stacked` as routine | Three seats is for high-risk changes the caller explicitly opted into. Default `layered` covers most changes. |
| Priming a semantic reviewer with the prior verdict | More seats over the same oracle repeat one blind spot. Give the contract and raw evidence, not the conclusion. |

## Why two passes

A sharp semantic pass and a mechanical pass are complementary, not redundant: the semantic pass
catches the cross-path / contract / test-quality bugs a linter never reaches, while the mechanical
pass catches the null-safety, doc-drift, unused-dep, dead-code, and invalid-generated-spec issues the
semantic pass skims past — typically several times more of them. Opposite framings, one synthesis, is
what closes the gap. Adding more semantic seats (`stacked`) helps only when each seat reviews against
an independent contract, not the previous verdict.

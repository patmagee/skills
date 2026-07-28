---
name: dual-adversarial-review
description: Run two adversarial reviewers (Claude Opus + Codex) in parallel against a spec, plan, or diff, then synthesize an accept/reject table. Use after writing a design/plan or before merging, when the user wants failure-mode review from both a Claude and a Codex perspective — or says "adversarial review", "dual review", "review with both".
---

# Dual Adversarial Review

Dispatch **two independent adversarial reviewers in parallel** — one Claude (Opus) and one Codex — against
the same artifact (spec, implementation plan, or code diff), then **synthesize** their findings into a
single accept/reject decision. The goal is failure modes, not approval.

## When to use

- After `writing-plans` / a design spec, before implementation (review the plan).
- Before requesting human review / merge (review the diff).
- Whenever the user asks for an adversarial, dual, or "review with both Claude and Codex" pass.

## Process

1. **Identify the artifact(s)** to review (file paths for a spec/plan, or the working diff / PR). Note the
   repo root and any conventions doc the reviewers should respect.

2. **Dispatch both reviewers in ONE message (parallel)**:
   - **Claude reviewer** — `Agent` tool, `subagent_type: general-purpose`, `model: opus`.
   - **Codex reviewer** — `Agent` tool, `subagent_type: codex:codex-rescue` (or invoke the `codex:rescue`
     skill). If Codex is unavailable, say so and run the Claude reviewer only.

   Give **both** the same prompt skeleton:
   > You are an adversarial reviewer. Find failure modes, correctness bugs, and gaps — do NOT approve, do
   > NOT be agreeable. Read <artifact paths>. <1–3 sentences of context>. **Verify every claim against
   > the real codebase** (name the key files to check). Attack especially: <the 4–8 highest-risk areas,
   > named concretely>. Output a numbered findings list, each tagged [BLOCKER]/[MAJOR]/[MINOR] with the
   > specific file/line or doc section, why it's wrong, and a concrete fix. If something is fine, omit it.
   > End with the top 3 things to fix. Review only — do not implement.

   Naming the high-risk areas yourself (concurrency, transactionality, dialect/version assumptions, RLS /
   tenant isolation, error/edge paths, data-loss windows) makes both reviews far sharper than a generic ask.

3. **Synthesize — do not blindly accept** (apply `superpowers:receiving-code-review` discipline):
   - **Filter noise.** When reviewing a *plan*, Codex often reports "this code doesn't exist yet" as
     BLOCKERs — those are not defects; discard them. Keep only findings that are wrong *given the artifact's
     stage*.
   - **Verify** each surviving finding against the code yourself before accepting (the reviewers can be
     wrong; so can you).
   - Produce an **accept/reject table**: finding → severity → accept or reject → one-line reason.
   - For accepted findings, fold the fix back into the spec/plan/code; for rejected ones, record why.

4. **Report**: the table, what changed, and the top remaining risks. Note convergence (both reviewers
   flagged X) — convergent findings are usually real.

## Notes

- Run reviewers **concurrently** (one message, two `Agent` calls) — they are independent.
- Keep your own context lean: the subagents return summaries; relay only the synthesized result.
- This skill reviews; it does not merge or implement. Hand fixes back to the normal edit/execution flow.
# Dual Adversarial Review

Dispatches two independent adversarial reviewers in parallel, one Claude (Opus) and
one Codex, against the same artifact (a spec, an implementation plan, or a code
diff), then synthesizes their findings into a single accept/reject table. The goal
is finding failure modes, not granting approval.

## When to use it

- After writing a plan or design spec, before implementation.
- Before requesting human review or merging a diff.
- Whenever you want a "review with both" pass: two models with different failure
  profiles, so convergent findings carry extra weight.

Trigger phrases: "adversarial review", "dual review", "review with both".

## How it works

1. Both reviewers get the same prompt: verify every claim against the real
   codebase, attack the named high-risk areas, and output severity-tagged findings.
2. The orchestrator filters noise (for example, Codex flagging not-yet-written code
   as a blocker when reviewing a plan), verifies each surviving finding against the
   code, and produces an accept/reject table with reasons.
3. Accepted fixes are folded back into the artifact; rejected findings are recorded
   with the reason.

## Dependencies

The Codex reviewer needs the Codex CLI plugin (`codex:codex-rescue`). If Codex is
unavailable, the skill says so and runs the Claude reviewer alone. Synthesis
references the `superpowers:receiving-code-review` skill; the discipline it
describes (verify before accepting) applies even without that skill installed.

---
title: experience-memory — knowledge-centric self-improvement for local Claude Code work
date: 2026-07-29
repo: claude-skills
services: [claude-skills]
tags: [workflow, devops]
status: active
human_reviewed: true
decisions:
  - Adapt the knowledge-centric self-improvement protocol (arXiv 2607.19592) as a standalone skill plus plugin hooks
  - Target everyday Claude Code work, design tasks, debugging, and oncall (not a benchmark task pool)
  - Hybrid capture, a Stop hook prompts and the skill executes
  - Global store at ~/.experience-memory/ with topic-keyed forum threads
  - Two-layer protocol (Approach B), stances folded into capture time, no separate cross-task forum stage
  - Threshold-triggered plus on-demand distillation, never automatic
  - SessionStart injects a small topic index; the model pulls full bundles on topic match
  - Standalone stdlib-only implementation, no ChromaDB or embeddings, separate from design-memory
---

# experience-memory: knowledge-centric self-improvement for local Claude Code work

## Background

The paper "Knowledge-Centric Self-Improvement" (arXiv 2607.19592) inverts the usual
agent self-improvement approach. Agents stay generic and disposable. The artifact that
improves is a shared, curated knowledge base that seeds each fresh agent. The protocol
has three stages: a task-level forum where agents post evidence-grounded claims after
each attempt, a cross-task forum where claims are tested for transferability with
explicit AGREE / DISAGREE / SYNTHESIZE stances, and a distillation stage where an LLM
selects surviving claims into compact typed bundles. The paper reports higher solve
rates at lower cost than agent-centric baselines (for example 86.7% vs 70% on
ARC-AGI-1 at roughly a third of the dollar cost), and shows that frozen bundles
transfer to held-out tasks and across model families.

This spec adapts that protocol to local, single-user Claude Code use.

[HUMAN DECISION]
The system targets everyday Claude Code work broadly: normal coding sessions, design
tasks, debugging, and oncall work. It is not limited to a benchmark-style pool of
retryable tasks.
[/HUMAN DECISION]

### Relationship to design-memory

design-memory (an existing skill in this repo) stores design decisions, which are
conclusions. This system stores tested claims: hypotheses with evidence, falsifiable
predictions, and explicitly rejected approaches. design-memory is append-only and its
entries are never challenged. Here, later sessions take stances against prior claims,
and falsified claims are retained as rejected hypotheses. The two are complementary
layers and share no infrastructure.

[CONFIRMED DECISION]
Build experience-memory as a standalone, stdlib-only skill with its own store. Do not
extend design-memory or reuse its ChromaDB and embedding stack. Topic matching happens
by the model reading a small injected index, so no vector retrieval sits in any hot
path. Cross-linking with design-memory can come later.
[/CONFIRMED DECISION]

## Protocol adaptation (Approach B)

[CONFIRMED DECISION]
Use a two-layer protocol. The paper's stage 1 (task-level forum) and stage 2
(cross-task forum) merge into capture time: each captured claim carries the full
evidential schema and must take a stance (NEW, AGREE, DISAGREE, or SYNTHESIZE) against
prior posts in its topic thread. Distillation remains a distinct stage. This works
locally because each new session already plays the role of the paper's
next-generation agent: it has fresh context, real execution evidence, and can read
the thread. The mechanisms the paper credits for its gains are all preserved:
evidence grounding, falsifiable predictions, disagreement as signal, rejected
hypotheses, and distillation as selection.
[/CONFIRMED DECISION]

The paper's "task" maps to a **topic**: a recurring unit of work such as
`flaky-ci-repo-x`, `mimir-alert-oncall`, or `kg-local-dev-setup`. Forum threads,
attempt tables, and bundles are all per-topic.

## Architecture

Three components, all inside `skills/experience-memory/` in this repo (hooks at the
plugin level):

1. **A stdlib-only Python CLI** (`scripts/experience.py`) that owns the store:
   schema validation, appends, thread reads, bundle swaps, index regeneration. All
   state mutations go through it. The model never hand-edits store files.
2. **Two plugin hooks** (shipped via the plugin's `hooks/hooks.json`):
   a SessionStart hook that injects the topic index, and a Stop hook that fires a
   capture reminder at most once per session, only when the session looks
   substantive.
3. **The skill** (SKILL.md plus agent prompts in `agents/`) orchestrating three
   flows: capture, pull, and distill.

### Store layout

[CONFIRMED DECISION]
One global store at `~/.experience-memory/`, topic-keyed. Not per-repo: debugging and
oncall knowledge recurs across repositories, and per-repo stores would starve
cross-task distillation of material.
[/CONFIRMED DECISION]

```
~/.experience-memory/
├── index.md                    # tiny; injected at SessionStart
├── topics/<topic-slug>/
│   ├── topic.json              # title, tags (repo, domain), counts, distill status
│   ├── attempts.jsonl          # typed attempt table
│   ├── posts.jsonl             # forum thread: claims with stances
│   └── bundle.md               # current distilled bundle
└── global/bundle.md            # cross-topic principles
```

Attempts and posts are append-only JSONL. Bundles are replaced atomically
(write temp file, then rename). Posts are never deleted: the thread is the permanent
record and the bundle is the curated view.

## Schemas

### Attempt record

One per captured session-topic pairing. Example:

```json
{"id": 4, "ts": "2026-07-29T14:02:11Z", "repo": "asserts-adi", "branch": "fix/onboarding",
 "task": "Get model-builder to cold-onboard dev stack 1729", "outcome": "partial",
 "verification": "graph built but relationship rules empty; checked FalkorDB node counts",
 "bundle_used": true}
```

- `outcome`: one of `solved | partial | failed | abandoned`.
- `verification`: how the outcome was determined. Required and non-empty; this forces
  the paper's discipline of grounding outcomes in checks rather than impressions.
- `bundle_used`: optional boolean recording whether a distilled bundle was pulled
  during the session. This is the system's only measurement loop.

### Post (claim)

The paper's six task-level fields plus the stance mechanism folded in from its
cross-task stage:

```json
{"id": 9, "attempt_id": 4, "ts": "2026-07-29T14:03:40Z",
 "claim": "Cold onboarding requires the gcom proxy env var even when metrics come from Mimir directly",
 "load_bearing_assumption": "model-builder reads GCOM_PROXY_URL at startup, not per-request",
 "evidence": "startup log: 'gcom client disabled, skipping tenant resolution' when var unset",
 "stance": "DISAGREE", "stance_post_id": 6,
 "proposed_change": "Set GCOM_PROXY_URL before first run instead of restarting mid-onboard",
 "predicted_outcome": "Fresh onboard with var set from the start completes relationship rules",
 "confidence": "medium"}
```

Validation enforced by the CLI:

- `evidence` non-empty.
- `stance` in `NEW | AGREE | DISAGREE | SYNTHESIZE`; non-NEW stances require a
  `stance_post_id` that exists in the same thread.
- `load_bearing_assumption`, `proposed_change`, `predicted_outcome`, and `claim`
  present and non-empty.
- `confidence` in `high | medium | low`.

Specificity requirements (the assumption must name a concrete tool, API, file, or
invariant; evidence must quote actual output; the prediction must be falsifiable) are
enforced by the capture prompt, not the validator, because they are not mechanically
checkable.

### Bundle

`bundle.md` uses the paper's six sections verbatim. Each entry cites post IDs so
claims stay auditable back to evidence.

```markdown
## Transferable insights      <- actionable, scoped, conditional guidance
## Confirmed constraints      <- verified environment or API requirements
## Rejected hypotheses        <- falsified approaches, with untried variants kept
## Pitfalls                   <- recurring errors and their triggers
## Checks                     <- validation strategies that caught real problems
## Next steps                 <- prioritized open questions
```

### Index

`index.md` holds one line per topic with a concrete hook, mirroring the MEMORY.md
pattern that is known to survive injection well:

```markdown
- kg-local-dev-setup — gcom proxy + cold onboarding gotchas [12 posts, bundle fresh]
- flaky-ci-asserts-adi — testcontainers port races [6 posts, 5 undistilled ⚡ distill ready]
```

The `⚡ distill ready` marker is how threshold triggering surfaces without any
background process.

## Capture flow

[CONFIRMED DECISION]
Hybrid capture: a Stop hook detects substantive sessions and injects a one-line
reminder; the skill owns the schemas and writes the posts. Fully automatic capture
would flood the store with noise; manual-only capture would depend on remembering.
[/CONFIRMED DECISION]

1. **Stop hook** (`hooks/capture-reminder.sh` wrapping a small Python helper).
   Receives the transcript path on stdin. Fires only when all three hold: the session
   has more than roughly 15 tool uses (cheap scan of the transcript JSONL), no capture
   has happened this session (marker file keyed by session ID in the scratchpad
   directory), and the store exists. On firing it emits one line of additional
   context: "Substantive session. If hypotheses were tested or something non-obvious
   was learned, run the experience-memory capture flow." It writes the marker
   immediately so it never fires twice, and any internal error exits 0 silently.

2. **Capture** (skill flow, triggered by the reminder or manually). The model, with
   the session still in context, performs four steps:
   - **Topic match**: run `experience.py topics`, match the session's work against
     existing topics, create a new topic only when nothing fits. Bias strongly toward
     reuse; fragmented topics kill the forum dynamics.
   - **Attempt record**: write outcome and verification via `experience.py attempt`.
   - **Read the thread**: `experience.py thread <topic>`. This step replaces the
     paper's stage-1 forum rounds and makes stances possible. The capture prompt
     requires engaging with prior claims: evidence that contradicts a prior post is a
     DISAGREE with citation, not a fresh NEW post.
   - **Post 1 to 3 claims** via `experience.py post`, schema-validated. The prompt
     enforces the paper's quality bars and rejects generic advice.

3. **Threshold surfacing**: `post` output includes the topic's undistilled count. At
   5 or more, the CLI prints a distill-ready notice and the model relays it. Nothing
   auto-runs.

Deliberate deviation from the paper: its agents post after every attempt, including
trivial ones. Locally, capture is gated on substance, because the corpus should grow
by sessions worth remembering, not by attempt count.

## Injection and pull

[CONFIRMED DECISION]
A SessionStart hook injects the small index; the model pulls the full bundle when the
session's work matches a topic. Per-prompt retrieval (UserPromptSubmit hook with
embeddings) was rejected as costly in the hot path; skill-trigger-only was rejected as
unreliable.
[/CONFIRMED DECISION]

- **SessionStart hook** injects `index.md` verbatim with a short preamble explaining
  what it is and how to pull a bundle. One line per topic keeps this to roughly a
  couple hundred tokens at 50 topics.
- **Pull**: before starting work that matches an index line, run
  `experience.py bundle <topic>` and treat the sections as prior evidence, with two
  required behaviors:
  - Do not repeat rejected hypotheses. If the bundle records an approach as falsified
    under given conditions, avoid it or state explicitly why this situation differs
    (which sets up a future DISAGREE post).
  - Run the bundle's checks early. The Checks section is validation that caught real
    problems before.
- **Global bundle**: pulled when the work is substantive but matches no topic. This
  is the local analogue of the paper's held-out-task transfer.
- **Timing gap, named**: SessionStart fires before the first prompt, so injection
  cannot be task-conditioned the way the paper's adapter memo is. Index-then-pull is
  the workaround: the model does the task-conditioning at the moment the task becomes
  clear. The cost is trigger reliability, which is why index lines carry concrete
  hooks rather than bare topic names.
- **Influence footer**: `bundle` output ends with a one-line reminder that capture
  should set `bundle_used` on the attempt record.

## Distillation

[CONFIRMED DECISION]
Threshold-triggered plus on-demand. Capture appends cheaply; when a topic's
undistilled post count crosses 5, the next capture or injection surfaces a
distill-ready notice. A manual command runs distillation at any time. Scheduled
background distillation was rejected (burns tokens unattended, drifts from active
work); on-demand-only was rejected (stale bundles quietly stop improving).
[/CONFIRMED DECISION]

Distillation runs as a fresh subagent, pinned to a Sonnet-tier model in the dispatch
(this is selection over a bounded thread, not hard reasoning). A fresh context is
deliberate: the distiller judges claims on cited evidence, not on the session that
produced them.

The distiller prompt (`agents/distiller.md`) receives the full thread, the attempt
table, and the current bundle, and rebuilds the bundle under the paper's rules:

- **Selection, not summarization.** Keep claims that are actionable,
  evidence-grounded, and scoped. Drop vague advice entirely rather than compressing
  it.
- **Resolve stances.** An AGREE chain raises a claim toward Confirmed constraints. A
  DISAGREE with stronger evidence moves the losing claim to Rejected hypotheses,
  narrowed to the tested parameterization, with untried variants of the same family
  preserved. A genuine unresolved conflict keeps both positions, marked FALSIFIED and
  UNTRIED with their evidence, never forced to consensus.
- **Failed predictions are signal.** Each post carries a falsifiable prediction;
  later attempt records show how predictions fared. Prediction-versus-outcome is the
  distiller's strongest evidence for promoting or demoting a claim.
- **Bundles do not grow monotonically.** Each distill rebuilds from thread plus prior
  bundle; superseded guidance is dropped. A target size cap of roughly 150 lines
  forces prioritization.

Mechanics: the distiller writes the new bundle to a temp file;
`experience.py distill <topic> --bundle-file <tmp>` validates the section structure,
atomically swaps `bundle.md`, advances a `distilled_through_post_id` watermark in
`topic.json` (posts.jsonl itself is never mutated), and regenerates `index.md`. The
undistilled count is the number of posts past the watermark.

**Cross-topic distillation** (`distill --cross`) applies the same pattern over all
topic bundles to produce `global/bundle.md`. Only principles evidenced in two or more
topics qualify. On-demand only; expected cadence is roughly monthly.

## Error handling

Ordered by blast radius:

- **Hooks fail silent.** Both hooks wrap everything in a catch-all and exit 0. A
  broken store or malformed transcript must never block a session. Worst case is a
  missed reminder or a missing index, and both flows remain manually invocable.
- **The CLI is the integrity boundary.** Schema violations exit non-zero with a
  message specific enough for the model to fix its payload and retry (for example,
  "stance DISAGREE requires stance_post_id; thread has posts 1-8"). Store directories
  auto-initialize on first write. A missing topic on read is an error listing valid
  topics, never an auto-create.
- **Concurrency.** Appends are single-line O_APPEND writes, atomic at this size on a
  local filesystem. Bundle swaps are write-temp-then-rename. Interleaved posts from
  two simultaneous sessions are harmless for JSONL. The one real race, two distills
  of the same topic at once, is guarded by a lock file with a stale-lock timeout.
- **Corrupt lines.** Readers skip unparseable JSONL lines with a warning to stderr
  rather than failing the read.

## Testing

- **Unit tests** (stdlib `unittest`, `tests/test_experience.py`, run via
  `python3 -m unittest discover`): schema validation accept and reject cases per
  field, stance and post-ID referential checks, threshold counting, index
  regeneration, bundle swap atomicity, corrupt-line tolerance, and lock behavior. The
  CLI takes a `--store` path override so tests run against a temp directory, never
  `~/.experience-memory/`.
- **Hook tests**: the Stop-hook logic is a Python function taking a transcript path
  and marker directory, unit-tested for fires and does-not-fire cases. The shell
  wrapper stays a thin exec.
- **End-to-end**: a documented walkthrough in the skill's CLAUDE.md. Seed a fake
  topic, capture twice with a DISAGREE, distill, verify bundle contents. Manual,
  because the interesting behavior is prompt-driven.

## Out of scope

Deliberate omissions, all additive later without store migration:

- No embeddings or vector search.
- No automatic distillation.
- No design-memory integration.
- No team-sharing or per-repo overlay.
- No metrics beyond the `bundle_used` boolean on attempt records.

## Success criteria

- Capture of a substantive session produces schema-valid attempt and post records in
  under a minute of session time.
- A topic with contradictory evidence across sessions ends up, after distillation,
  with a narrowed rejected hypothesis rather than two contradictory tips.
- A fresh session on a known topic pulls the bundle and demonstrably avoids a
  recorded rejected hypothesis.
- The SessionStart injection stays under roughly 300 tokens at realistic topic
  counts.

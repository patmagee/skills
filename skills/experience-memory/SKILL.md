---
name: experience-memory
description: >
  Knowledge-centric self-improvement for local Claude Code work, adapted from
  arXiv 2607.19592. Maintains a global store (~/.experience-memory/) of
  topic-keyed forum threads: evidence-grounded claims with stances, typed
  attempt records, and distilled bundles that seed future sessions. Use this
  skill when: a Stop-hook reminder says the session was substantive and worth
  capturing; the user says "capture this session", "post experience",
  "remember what we learned", "what have we learned about X", or "distill
  topic X"; the SessionStart index shows a topic matching work about to start
  (pull the bundle first); or a topic is marked distill ready. Covers the
  capture flow (attempt record plus claims with stances), the pull flow
  (bundle retrieval before matching work), and the distill flow (subagent
  selection into a typed bundle).
---

# experience-memory

A local implementation of knowledge-centric self-improvement: sessions stay
disposable, and the artifact that improves is a curated knowledge store.
All store mutations go through the CLI; never edit store files by hand.

    python3 <this-skill-dir>/scripts/experience.py <command> [args]
    # every command accepts --store <path>; default is ~/.experience-memory

Read `references/schemas.md` before writing any payload.

## Pull flow (start of matching work)

Trigger: the SessionStart index (an `<experience-memory-index>` block) lists
a topic matching the work about to start.

1. Run `experience.py bundle <topic-slug>` and read it as prior evidence.
2. Do not repeat Rejected hypotheses. If you believe this situation differs
   from the falsified conditions, say so explicitly; that sets up a DISAGREE
   post at capture time.
3. Run the bundle's Checks early; they caught real problems before.
4. Remember that a bundle was used: the capture-flow attempt record must set
   `"bundle_used": true`.

If the work is substantive but matches no topic, pull the global bundle:
`experience.py bundle --global` (skip silently if it does not exist yet).

## Capture flow (end of substantive work)

Trigger: the Stop-hook reminder, or the user asks to capture.

Worth capturing means hypotheses were tested or something non-obvious was
learned. Routine sessions with nothing generalizable are NOT captured; tell
the user so and stop. Never capture secrets, tokens, or customer data in any
field.

1. **Topic match.** Run `experience.py topics`. Match the session's work
   against existing topics; bias strongly toward reuse. Create a new topic
   only when nothing fits:
   `experience.py create <slug> --title "..." --hook "<concrete gotcha line>"
   --tags <repo>,<domain>`.
2. **Attempt record.** `experience.py attempt <slug> --json '<payload>'`
   per `references/schemas.md`. Outcome and verification are about what
   actually happened, including failures; set `bundle_used` truthfully.
3. **Read the thread.** `experience.py thread <slug>`. This step is
   mandatory before posting: stances against prior claims are the point of
   the system.
4. **Post 1 to 3 claims.** `experience.py post <slug> --json '<payload>'`.
   Apply every quality bar in `references/schemas.md`. If the CLI rejects a
   payload, fix the named field and retry.
5. **Relay the threshold.** If the CLI prints `distill ready`, tell the user
   and offer to run the distill flow now. Never distill without asking.

## Distill flow (on request or when a topic is distill ready)

1. Collect inputs: `experience.py thread <slug>` output and, if present,
   `experience.py bundle <slug>` output.
2. Dispatch a subagent (Sonnet tier; this is selection over a bounded
   thread, not hard reasoning). Its prompt is the full content of
   `agents/distiller.md` followed by the collected inputs. It returns the
   new bundle text plus a final `HOOK: ...` line.
3. Strip the HOOK line, write the bundle text to a temp file, then install:
   `experience.py distill <slug> --bundle-file <tmp> --hook "<hook text>"`.
4. If the CLI rejects the bundle (missing or out-of-order sections),
   re-dispatch the distiller once with the error appended; if it fails
   again, report the error and stop.
5. Confirm to the user: watermark position and one line on what changed in
   the bundle.

**Cross-topic distill** (user asks, roughly monthly): collect every topic's
`bundle.md` via `experience.py bundle <slug>` for each topic, dispatch the
distiller with all of them and the instruction that only principles
evidenced in two or more topics qualify, then install with
`experience.py distill --cross --bundle-file <tmp>`.

## Bootstrap

The store does not exist until the first `create`. Hooks are silent no-ops
until then, so the whole system is opt-in: the first capture creates it.

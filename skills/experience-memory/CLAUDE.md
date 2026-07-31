# CLAUDE.md — experience-memory

## Architecture

Three layers with strict responsibilities:

- `scripts/experience.py` — the integrity boundary. All store mutations go
  through it: schema validation, appends, atomic bundle swaps, watermark,
  index regeneration. Append-only JSONL for attempts/posts; watermark
  (`distilled_through_post_id` in topic.json) instead of mutating posts.
- `scripts/stop_hook.py` + `hooks/` (plugin root) — timing. SessionStart
  injects `index.md`; Stop fires a one-shot reminder for substantive
  sessions (>15 tool uses, marker per session under `<store>/markers/`).
  Hooks always exit 0 and never print on internal error.
- `SKILL.md` + `agents/distiller.md` + `references/schemas.md` — judgment.
  What is worth capturing, topic matching, stance discipline, distillation
  rules (selection not summarization, stance resolution, prediction vs
  outcome, no monotonic growth).

Spec: `docs/superpowers/specs/2026-07-29-experience-memory-design.md`.

## Tests

    cd skills/experience-memory && python3 -m unittest discover -s tests -v

All tests run against temp-dir stores via `--store`; never the real store.

## End-to-end walkthrough (manual)

    export EXPERIENCE_STORE=/tmp/em-e2e && rm -rf "$EXPERIENCE_STORE"
    CLI="skills/experience-memory/scripts/experience.py"
    python3 $CLI --store "$EXPERIENCE_STORE" create flaky-ci-demo \
      --title "Flaky CI demo" --hook "testcontainers port races" --tags demo
    python3 $CLI --store "$EXPERIENCE_STORE" attempt flaky-ci-demo --json \
      '{"task":"fix flaky pg test","outcome":"failed","verification":"3 runs, 2 failures"}'
    python3 $CLI --store "$EXPERIENCE_STORE" post flaky-ci-demo --json \
      '{"attempt_id":1,"claim":"retry masks a port race","load_bearing_assumption":"testcontainers maps 5432 before ready","evidence":"log: connection refused then success on retry","stance":"NEW","stance_post_id":null,"proposed_change":"wait on readiness probe not sleep","predicted_outcome":"0 failures in 5 runs with probe","confidence":"medium"}'
    python3 $CLI --store "$EXPERIENCE_STORE" attempt flaky-ci-demo --json \
      '{"task":"retry with readiness probe","outcome":"solved","verification":"5 clean runs"}'
    python3 $CLI --store "$EXPERIENCE_STORE" post flaky-ci-demo --json \
      '{"attempt_id":2,"claim":"probe fixes it; sleep-based waits were the cause","load_bearing_assumption":"pg readiness = accepting connections, not container started","evidence":"5 clean runs after probe swap","stance":"AGREE","stance_post_id":1,"proposed_change":"apply probe pattern to redis tests too","predicted_outcome":"redis tests also stabilize with probe","confidence":"high"}'
    python3 $CLI --store "$EXPERIENCE_STORE" thread flaky-ci-demo
    # write a six-section bundle to /tmp/em-bundle.md by hand or via the
    # distiller prompt, then:
    python3 $CLI --store "$EXPERIENCE_STORE" distill flaky-ci-demo \
      --bundle-file /tmp/em-bundle.md --hook "pg port races: probe not sleep"
    python3 $CLI --store "$EXPERIENCE_STORE" bundle flaky-ci-demo
    cat "$EXPERIENCE_STORE/index.md"   # expect: bundle fresh, new hook
    rm -rf "$EXPERIENCE_STORE" && unset EXPERIENCE_STORE

Expected at each step: exit 0, and after distill the index shows
`bundle fresh` with the updated hook. To exercise a DISAGREE, add a third
post with `"stance":"DISAGREE","stance_post_id":1` and re-distill: the
losing claim should land under Rejected hypotheses, narrowed.

## Modification notes

- New post fields: add to `POST_REQUIRED_FIELDS` (or optional handling) in
  `experience.py`, to `references/schemas.md`, and to the tests. The store
  needs no migration for additive fields.
- Threshold and caps are constants at the top of `experience.py`
  (`DISTILL_THRESHOLD`, `BUNDLE_SIZE_WARN_LINES`) and `stop_hook.py`
  (`TOOL_USE_THRESHOLD`).
- Bundle section names are load-bearing in three places: `BUNDLE_SECTIONS`,
  `agents/distiller.md`, `references/schemas.md`. Change all or none.

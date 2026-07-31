# experience-memory

Knowledge-centric self-improvement for local Claude Code work, adapted from
["Knowledge-Centric Self-Improvement" (arXiv 2607.19592)](https://arxiv.org/abs/2607.19592).

The idea, inverted from most self-improvement schemes: sessions stay
disposable, and the thing that improves is a curated knowledge store.
Sessions post evidence-grounded claims into per-topic forum threads, take
explicit stances (AGREE / DISAGREE / SYNTHESIZE) against earlier claims, and
a distiller periodically selects the survivors into a compact bundle that
seeds future sessions. Falsified approaches are kept as rejected hypotheses,
which is precisely the knowledge a plain lessons-learned log loses.

## How it works day to day

- **SessionStart**: a hook injects a one-line-per-topic index.
- **During work**: when the session matches a topic, Claude pulls the
  topic's bundle, avoids its rejected hypotheses, and runs its checks early.
- **Stop**: after a substantive session, a hook reminds Claude once to offer
  capture: an attempt record (outcome plus how it was verified) and one to
  three schema-validated claims with stances against the existing thread.
- **When a topic accumulates 5 undistilled posts**: it is marked distill
  ready; a fresh subagent rebuilds the bundle by selection, never
  summarization.

## Layout

Store: `~/.experience-memory/` (override with `--store` or the
`EXPERIENCE_STORE` env var for the hooks).

    topics/<slug>/{topic.json, attempts.jsonl, posts.jsonl, bundle.md}
    global/bundle.md    # cross-topic principles
    index.md            # injected at SessionStart

Everything is stdlib-only Python plus two small bash hook wrappers. The
store is opt-in: hooks stay silent until the first topic is created.

## Relationship to design-memory

design-memory (also in this repo) stores design *decisions*; this stores
tested *claims* with evidence and falsification. They are complementary
layers and share no infrastructure.

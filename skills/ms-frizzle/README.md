# Ms. Frizzle

A skill for directed experimentation: learning how something actually works through
hands-on probes, before there is a spec or a known deliverable.

## When to use it

Use this skill when the goal is understanding, not a finished artifact. Typical
prompts: "let's poke at X", "I want to understand how Y actually works", "what
would happen if", "field trip", or an explicit `/ms-frizzle`.

Do not use it when the deliverable is already known (use a brainstorming or
spec-driven flow instead), and do not use it for unbounded autonomous looping.

## How it works

The skill structures the session as a field trip:

1. **Board the bus.** Name exactly one driving question, set a budget (default six
   legs or one working session), pick an isolated workspace, and open a journal.
2. **Ride one leg at a time.** Each leg is a single experiment with a falsifiable
   guess written down first. The result is recorded immediately, and a ledger
   tracks open questions, settled findings, and dead ends.
3. **Watch the road.** The trip ends when the question is answered, the budget is
   spent, or two consecutive legs teach nothing new.
4. **Come home.** The session ends with a forced synthesis: a one-or-two sentence
   answer to the driving question, a recommended starting point for a real build,
   and a decision about which artifacts to keep.

The deliverable is the findings journal, written incrementally during the trip.
Probe code is treated as evidence, not product, unless it is explicitly tagged as
worth salvaging.

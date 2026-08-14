# Investigate

A skill for working through an incident, a regression, or a production mystery
that you need to understand, not just resolve.

## The problem it solves

During a multi-week production incident, AI-assisted work did what it is good
at: mitigations were designed and shipped quickly, and their effect was
evaluated quickly. What did not happen was comprehension. Nobody involved
could say where Claude had looked, what it had ruled out, what it had failed
to check, or why the eventual resolution worked.

Handing investigation to an AI removes exactly the two steps that produce
understanding: forming the next question, and investigating it. The human is
left holding a summary rather than a picture. This skill keeps the
investigating step with Claude, because speed there is the entire reason to
use an AI. It gives the evaluating, questioning, and synthesizing steps back
to the human.

## When to use it

Use it when you want to understand something, not merely resolve it: an
incident, a regression, or a production mystery. Typical triggers: `/investigate`,
"help me understand this incident", or "I do not want the answer, I want to
understand it".

## The six beats

Every step of the investigation runs the same loop, in order:

1. **Orient.** Claude states what is currently known as a numbered list, each
   item carrying its state, then says what has not been checked yet.
2. **Question.** You name the next question to investigate. Claude may hand
   you candidate questions if you ask for them, but the trail records that the
   question was suggested rather than formed by you.
3. **Investigate.** Claude gathers evidence and reports four things: the query
   it ran, the values that came back, what those values rule out, and what it
   could not check, with the reason why.
4. **Wait.** Claude asks what you make of the evidence, then stops. Nothing
   else lands in that message.
5. **Confirm or correct.** Claude acknowledges what you got right. If your
   answer is vague, it points at the specific rows or lines in the trail
   rather than supplying the reading itself.
6. **Record.** Claude appends the claim to the trail in your own words, then
   the loop returns to beat one.

## The two hard rules

**Evidence is reported raw and never characterized.** Claude shows the values
that came back, trimmed for length but not summarized. It will not describe a
number as elevated, normal, spiking, or healthy. The moment it characterizes a
value, it has done your interpreting for you, which is the failure this skill
exists to prevent.

**Claude never answers its own question in the same message.** If it poses a
question at beat four, that message ends there.

These two rules are the spine of the skill. They are not checked by any
script; only a human reading the transcript can tell whether Claude actually
held to them. See `CLAUDE.md` in this directory for what the linter does and
does not check.

## A worked trail excerpt

Every investigation produces one trail file: a findings table, an append-only
evidence log, a gap ledger of what was never checked, and a synthesis in the
human's own words. Here is an excerpt from
`references/sample-trail.md`, a worked example:

```markdown
## Findings

| id | claim | state | evidence | framed by |
|----|-------|-------|----------|-----------|
| F1 | Replica pods restart during trim cycles; masters do not. | reasoned | E1 | human |
| F2 | Restarts are caused by container memory pressure. | refuted | E2 | human |
| F3 | Trim load arrives alongside cluster rebalance. | accepted | E3 | claude |
| F4 | Whether the liveness probe timeout is the trigger. | open | | human |

## Evidence

### E1

- form: metrics
- target: `grafanacloud-prom`
- query: `sum by (pod) (increase(kube_pod_container_status_restarts_total{namespace="asserts"}[1h]))`
- window: `2026-08-10T14:00:00Z` to `2026-08-10T18:00:00Z`
- replayable: yes
- returned:

  ```
  {pod="falkordb-03-node-1"}  4
  {pod="falkordb-03-node-2"}  3
  {pod="falkordb-03-node-0"}  0
  ```
```

Notice what the excerpt shows about the four finding states. `F2` is
`refuted`: the memory-pressure claim was checked and eliminated, and it stays
in the file worth as much as a confirmed claim would. `F3` is `accepted`
rather than `reasoned` because Claude supplied that reading from a `kubectl
get events` shell record and the human took it, not because the human worked
it out from the evidence. `F4` is `open`: framed, but not yet investigated.
The full file also carries a "Not checked" gap ledger and a synthesis section,
written in the human's own words at close-out.

## Three ways in

- **Cold start.** You pass the opening question as an argument. Claude creates
  the trail file and begins at beat one with an empty findings table.
- **Resume.** You pass a path to an existing trail. Claude reads it, rebuilds
  the findings and the gap ledger, and continues from there.
- **Mid-session adoption.** You invoke the skill with no arguments partway
  through a session that is already running. Claude reconstructs the trail
  from the conversation so far, recording everything already established as
  `accepted` rather than `reasoned`, because you did not reason through it
  inside the loop.

Mid-session adoption is the common case in practice: nobody knows at the start
of a question that it is going to become a two-week incident.

## Checking a trail

A trail file's structure can be checked automatically:

```bash
python3 skills/investigate/scripts/lint_trail.py <trail.md>
```

This confirms the file is well-formed: every finding cites evidence that
exists, every evidence record carries the fields its form requires, and so
on. It cannot confirm that Claude held to the two hard rules above; that
still needs a human reading the transcript.

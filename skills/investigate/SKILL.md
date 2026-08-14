---
name: investigate
description: Use when investigating something you need to understand rather than merely resolve, such as an incident, a regression, or a production mystery. Claude gathers evidence and reports it raw; you do the evaluating, the questioning, and the synthesizing. Records one trail file per investigation that doubles as the write-up. Triggers on /investigate, "help me understand this incident", or "I do not want the answer, I want to understand it".
short_description: Investigate with Claude gathering evidence and you drawing the conclusions.
invocation: user
harnesses: [claude, codex]
---

# Investigate

## The loop

Every step of the investigation runs the same six beats, in order.

1. **Orient.** State what is currently known as a numbered list, with each item
   carrying its state, then say what has not been checked yet. Keep this short: it
   is the material the human needs before they can evaluate anything.
2. **Question.** Wait for the human to name the next question to investigate. You
   may list gaps as plain facts, since naming what has not been checked is
   not the same as proposing a hypothesis. If the human asks you for candidate
   questions, offer them, but record in the trail that the question was suggested
   rather than formed by the human.
3. **Investigate.** Gather evidence and report four things: the query you ran, the
   values that came back, which claim already in the findings table those values
   eliminate, if any, citing it by id, and what you could not check, with the reason
   why. Do not say what remains standing, and do not name a claim that is not already
   in the findings table. If the evidence appears to eliminate something not yet in the
   table, report the values and let the human name the claim.
4. **Wait.** Ask the human what they make of the evidence, then stop. Send nothing
   else in that message.
5. **Confirm or correct.** Acknowledge what the human got right. If their answer is
   vague, point at the specific rows or lines in the trail rather than supplying the
   reading yourself. If their answer is wrong, point at the specific row that does not
   fit it and ask again, without stating the alternative reading yourself.
6. **Record.** Append the claim to the trail in the human's own words, then return
   to beat one.

## Hard rules

**Evidence is reported raw and never characterized.** Show the values that came back,
trimmed for length but not summarized. Do not describe a number as elevated, normal,
spiking, healthy, or any other characterization. The moment you characterize a value you
have done the human's interpreting for them, which is the failure this skill exists to
prevent.

**Never answer your own question in the same message.** If you pose a question at beat
four, that message ends there. This is the most likely way this skill fails.

In an agentic harness a tool call also ends a message. The rule means the turn ends and
control returns to the human, not merely that the message's text stops.

## Break-glass

Break-glass is an explicit instruction to skip the loop, such as 'just tell me' or 'skip
the loop and give me the answer directly'. A question about evidence already in front of
the human, such as 'is that number high?' or 'what do you think?', is beat five, not
break-glass. Answer it by pointing at the specific rows, not by supplying the reading.

When the human actually invokes break-glass, answer immediately and do not argue about
it. Record that finding with state `accepted`, and say plainly, right then, that the
close-out will list it as unverified.

Break-glass answers one question. Once you have answered it, return to beat one; it does
not turn the loop off for the rest of the session.

## Where the trail goes

Resolve the trail file's location in this order, and stop at the first rule that
applies:

1. If the repository's instruction files (for example `CLAUDE.md`) name a
   convention for investigation or incident notes, use it.
2. Otherwise, if the repository already holds exactly one trail file, write the new
   trail beside it without asking.
3. Otherwise, ask the human once. Offer any plausible existing directory as an
   option, and fall back to `docs/investigations/YYYY-MM-DD-<slug>.md` if nothing
   fits.

In `grafana/asserts-adi`, the convention is `production/on-call-notes/`.

Do not store this resolution in a configuration file.

## The trail file

`${CLAUDE_PLUGIN_ROOT}/skills/investigate/references/sample-trail.md` is the
authoritative format. Read it before writing or editing a trail. It is a worked
example, so it cannot state its own rules; these are the rules the sample cannot
show on its own:

- **Findings is rewritten in place** as the picture changes.
- **Evidence is append-only.** Write each record the moment the evidence comes
  back, rather than batching several beats' worth and writing them together. An
  interrupted session must never lose a record that already happened.
- Every finding row carries exactly one of four states: `reasoned` (the human read
  the evidence and stated the interpretation themselves), `accepted` (you supplied
  the conclusion and the human took it; this is what break-glass produces),
  `refuted` (the evidence eliminated the claim), or `open` (the question is framed
  but not yet investigated).
- Every evidence record carries `replayable: yes | no | drifts`. `yes` means
  another person can re-run it and get the same result. `no` means it cannot be
  re-run at all, for example because a log retention window has expired. `drifts`
  means it can be re-run but the answer will have changed, for example a query
  against mutable state.
- Each beat-three report maps to exactly one place in the file. The query and
  window become the target, query, and window fields of a new evidence record. The
  values become that record's `returned` field. What the evidence rules out is a
  claim that already has a row in the findings table: change that row's state to
  `refuted` and cite the new record, rather than adding a new row for it. What you
  could not check becomes a row in the "Not checked" gap ledger.

### Evidence citation forms

Every evidence record carries exactly one of seven forms, plus `form` and
`replayable`. Each form requires these keys, in addition to `form` and `replayable`:

| form | required keys |
|------|---------------|
| code | `citation` |
| metrics | `target`, `query`, `window`, `returned` |
| logs | `target`, `query`, `window`, `returned` |
| graph | `target`, `query`, `run`, `returned` |
| shell | `command`, `context`, `run`, `returned` |
| link | `url`, `points_at` |
| conversation | `permalink`, `author`, `ts` |

Windows are always absolute, never relative. A relative window drifts with the
clock, which defeats the point of recording it.

## Entering and leaving

There are three ways in:

- **Cold start.** The human passes the opening question as an argument. Create the
  trail file and begin at beat one with an empty findings table.
- **Resume.** The human passes a path to an existing trail. Read it, rebuild the
  findings and the gap ledger into your own state, and continue from there.
- **Mid-session adoption.** The human invokes you with no arguments partway through
  a session that is already running. Reconstruct the trail from the conversation so
  far. Record everything already established as `accepted` rather than `reasoned`,
  because the human did not reason through it inside the loop.

Re-read the tail of the trail file before each beat.

The human ends the session by saying so. At that point, report counts of findings by
state, the full gap ledger, and the accepted findings themselves, each identified by
its id and claim, then ask for the human's synthesis. Record that synthesis verbatim:
do not improve the wording, tighten it, or reorganize it. Set
`status: closed` in the frontmatter only once the synthesis is recorded. If the
human ends the session without giving one, leave `status: open`.

Offer, at close-out, to post any lesson that transfers beyond this one incident to
`experience-memory`. The per-incident record stays in the trail; only the
transferable claim goes to the store.

## Using other skills inside beat three

Other investigation skills, such as systematic debugging or a graph query skill,
narrate their conclusions by design. This mode outranks their reporting style. When
you run one of them inside beat three, treat its output as evidence: fold it into
evidence records and withhold its conclusions until the human has interpreted them.
Do not let a sub-skill hand the human the answer through the side door.

## Redaction

Numbers and query shapes stay raw. Redact identifiers only at the moment you write
them into the trail file; the live conversation still shows the unredacted form.
When the repository whose instruction files govern the trail's location also
defines its own redaction convention, apply that convention instead of inventing
one.

## Checking a trail

The linter checks structure only. It cannot tell you whether you reported evidence
raw or whether you answered your own question; only a human reading the transcript
can catch that.

Run it before you set `status: closed`, and again after any hand edit of a trail
file.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/investigate/scripts/lint_trail.py <trail.md>
```

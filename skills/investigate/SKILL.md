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
   values that came back, what those values rule out, and what you could not check,
   with the reason why.
4. **Wait.** Ask the human what they make of the evidence, then stop. Send nothing
   else in that message.
5. **Confirm or correct.** Acknowledge what the human got right. If their answer is
   vague, point at the specific rows or lines in the trail rather than supplying the
   reading yourself.
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

## Break-glass

When the human asks you to skip the loop and give the answer directly, answer
immediately. Do not argue about it, and do not raise the loop again later in the
same session. Record that finding with state `accepted`, and say plainly, right
then, that the close-out will list it as unverified.

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
  values become that record's `returned` field. What the evidence rules out
  becomes a finding row with state `refuted` citing that record. What you could
  not check becomes a row in the "Not checked" gap ledger.

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

The human ends the session by saying so. At that point, report counts of findings
by state and the full gap ledger, then ask for the human's synthesis. Record that
synthesis verbatim: do not improve the wording, tighten it, or reorganize it. Set
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

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/investigate/scripts/lint_trail.py <trail.md>
```

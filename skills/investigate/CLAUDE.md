# CLAUDE.md — investigate

## How the mode is enforced

The six beats and the two hard rules (evidence reported raw, never answering
its own question in the same message) are enforced by instruction only.
Nothing in this skill stops Claude from drifting: characterizing a value, or
posing and answering a question in one message, is a prompting failure that a
future session can make again.

The deliberate escalation, if drift is observed in practice, is to move beat
three (Investigate) into a subagent whose only permitted output is evidence
records. That would make the restraint structural rather than something
Claude has to keep remembering. This is recorded as **deferred**, not as a
gap. The deferral holds until instruction enforcement is observed to drift,
on the view that building the subagent boundary before there is evidence of
drift would be solving a problem that has not shown up yet.

## What the linter checks, and what it cannot

`scripts/lint_trail.py` checks structure only: every finding row has a state
drawn from the four permitted values, every non-`open` finding cites evidence
that exists, every evidence record carries the fields its form requires
(including `replayable`), evidence ids are unique, the gap ledger section is
present, and a `status: closed` trail has a non-empty synthesis.

The two hard rules that carry the design are not on that list, because they
are not machine-checkable. Whether evidence was reported raw rather than
characterized, and whether Claude answered its own question in the same
message it asked it, can only be judged by a human reading the transcript.
Do not extend the linter to imply otherwise, and do not describe a clean lint
run as evidence that a trail followed the two hard rules; it only means the
file is well-formed.

## Why frontmatter is parsed by hand

`lint_trail.py` is Python standard library only. Skill scripts in this
repository cannot assume PyYAML is installed, so `parse_frontmatter` in
`scripts/lint_trail.py` splits the leading `---` block itself and reads it as
flat `key: value` lines, rather than calling a YAML library. This is
sufficient because trail frontmatter is always flat scalars; it would not be
sufficient if a future field needed a list or a nested value.

## `references/sample-trail.md` is dual-purpose

This file is both the format documentation that `SKILL.md` points to (read it
before writing or editing any trail) and the happy-path fixture that
`tests/test_lint_trail.py` lints and expects to pass. Editing the sample to
improve the prose changes what the tests assert against. Treat any edit to
this file as a test-affecting change: rerun the tests in this skill's `tests/`
directory before committing.

## Running the tests

    python3 -m unittest discover -s skills/investigate/tests

CI runs this same command, looped across every `skills/*/tests` directory, as
a step in `.github/workflows/ci.yml`. That step must not gain a `-t .` (top
level directory) argument. With `-t .` added, `unittest discover` treats the
repository root as the package root and fails with `ImportError: Start
directory is not importable`, because neither `skills/investigate/tests` nor
the other skills' `tests` directories have an `__init__.py`. The omission is
deliberate, not an oversight: it looks like the kind of thing a maintainer
would "clean up" into a broken build, so leave it as `-s "$dir"` with no `-t`.
